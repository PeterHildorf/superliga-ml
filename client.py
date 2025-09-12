from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import TimeSeriesSplit
from sklearn.metrics import brier_score_loss, log_loss
import pandas as pd, numpy as np
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
PARQ_DIR = PROJECT_ROOT / "data" / "parquet"
IN_FILE  = PARQ_DIR / "fixtures_superliga_2021_2023.parquet"
OUT_FILE = PARQ_DIR / "preds_superliga_2021_2023.parquet"

df = pd.read_parquet(IN_FILE)

# Kun afsluttede kampe og kronologisk orden (vigtigt for TimeSeriesSplit)
df = df[df["status"]=="FT"].copy()
df["date"] = pd.to_datetime(df["date"])
df = df.sort_values("date").reset_index(drop=True)

def long_format(df):
    home = df[["date","season","round","home","away","home_goals","away_goals"]].rename(
        columns={"home":"team","away":"opp","home_goals":"gf","away_goals":"ga"}
    )
    home["is_home"]=1
    away = df[["date","season","round","home","away","home_goals","away_goals"]].rename(
        columns={"away":"team","home":"opp","away_goals":"gf","home_goals":"ga"}
    )
    away["is_home"]=0
    out = pd.concat([home,away], ignore_index=True)
    out["pts"] = np.select([out["gf"]>out["ga"], out["gf"]==out["ga"]],[3,1], default=0)
    return out.sort_values(["team","date"])

lf = long_format(df)
lf["form5"] = lf.groupby("team")["pts"].rolling(5, min_periods=1).mean().reset_index(level=0, drop=True)
lf["gd5"]   = (lf["gf"]-lf["ga"]).groupby(lf["team"]).rolling(5, min_periods=1).sum().reset_index(level=0, drop=True)
lf["gf5"]   = lf.groupby("team")["gf"].rolling(5, min_periods=1).mean().reset_index(level=0, drop=True)
lf["ga5"]   = lf.groupby("team")["ga"].rolling(5, min_periods=1).mean().reset_index(level=0, drop=True)

feat_home = lf[lf["is_home"]==1][["date","team","form5","gd5","gf5","ga5"]].rename(columns={"team":"home"})
feat_away = lf[lf["is_home"]==0][["date","team","form5","gd5","gf5","ga5"]].rename(columns={"team":"away"})
X = df.merge(feat_home, on=["date","home"], how="left").merge(feat_away, on=["date","away"], how="left", suffixes=("","_away"))

y = (X["home_goals"] > X["away_goals"]).astype(int)
features = ["form5","gd5","gf5","ga5","form5_away","gd5_away","gf5_away","ga5_away"]
X_feat = X[features].fillna(0).to_numpy()

print("Class balance (home win):", y.mean().round(3), f"({y.sum()}/{len(y)})")

tscv = TimeSeriesSplit(n_splits=5)
probs = np.zeros(len(X_feat), dtype=float)

for train_idx, test_idx in tscv.split(X_feat):
    mdl = LogisticRegression(max_iter=1000)
    mdl.fit(X_feat[train_idx], y.iloc[train_idx])
    probs[test_idx] = mdl.predict_proba(X_feat[test_idx])[:,1]

print("Brier:", brier_score_loss(y, probs))
print("LogLoss:", log_loss(y, probs))

Xout = X[["date","home","away"]].copy()
Xout["p_home_win"] = probs
OUT_FILE.parent.mkdir(parents=True, exist_ok=True)
Xout.to_parquet(OUT_FILE, index=False)
print("Gemte:", OUT_FILE)
