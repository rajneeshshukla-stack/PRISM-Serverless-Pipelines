"""Build per-minute pipeline-arrival CSVs (minute,count) from the Huawei Private 2023
requests-per-minute trace, days 28-55 (28 consecutive days), by binomial thinning to a
mean of 600 executions/min (shape preserved). Deterministic (seed per function)."""
import numpy as np, pandas as pd, json, hashlib
X=np.load('X28.npy'); cols=pd.read_csv('cols.csv').iloc[:,0].astype(str).tolist()
FUN=['150','72','60','183','42']
meta={}
for i,f in enumerate(FUN):
    x=X[:,cols.index(f)]
    p=600.0/x.mean(); assert p<=1
    rng=np.random.default_rng(20261031+int(f))
    y=rng.binomial(x,p)
    pd.DataFrame({'minute':np.arange(len(y)),'count':y}).to_csv(f'huawei_fn{f}.csv',index=False)
    h=y.reshape(4,7*1440).mean(1)
    meta[f]=dict(source_mean=float(x.mean()),thin_p=p,mean=float(y.mean()),week_means=h.round(1).tolist(),
                 p999_over_median=float(np.percentile(y,99.9)/max(np.median(y),1)),
                 sha256=hashlib.sha256(y.astype(np.int64).tobytes()).hexdigest())
    print(f,meta[f])
json.dump(meta,open('traces_meta.json','w'),indent=1)
