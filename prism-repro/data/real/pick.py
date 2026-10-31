import pandas as pd, numpy as np
fs=[f'requests_minute/day_{d:03d}.csv' for d in range(28,56)]
D=pd.concat([pd.read_csv(f) for f in fs],ignore_index=True)
assert len(D)==28*1440, len(D)
t=D['time']; assert (np.diff(t.values)==60).all()
X=D.drop(columns=['day','time'])
nan=X.isna().mean(); X0=X.fillna(0)
mean=X0.mean(); 
rows=[]
for c in X.columns:
    x=X0[c].values
    if mean[c]<50: continue
    h=x.reshape(28,1440)
    daily=h.mean(1)
    dprof=h.mean(0); diurnal=dprof.std()/max(dprof.mean(),1e-9)
    d1=np.diff(x); 
    burst=np.percentile(x,99.9)/max(np.median(x),1)
    zero=(x==0).mean()
    wk=[daily[i*7:(i+1)*7].mean() for i in range(4)]
    rows.append((c,round(mean[c]),round(nan[c],3),round(zero,3),round(diurnal,2),round(burst,1),[round(w) for w in wk]))
rows.sort(key=lambda r:-r[1])
print(len(rows))
for r in rows[:45]: print(r)
np.save('X28.npy',X0.values.astype(np.int64)); pd.Series(X.columns).to_csv('cols.csv',index=False)
