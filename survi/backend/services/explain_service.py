import pandas as pd, numpy as np
from .ml_service import model,FEATURES
def explain(f):
 m=model(); X=pd.DataFrame([f])[FEATURES]; transformed=m.named_steps['preprocessor'].transform(X); names=m.named_steps['preprocessor'].get_feature_names_out(); clf=m.named_steps['model']; source='SHAP'
 try:
  import shap
  vals=shap.TreeExplainer(clf).shap_values(transformed)
  if isinstance(vals,list): arr=np.asarray(vals); idx=int(np.argmax(clf.predict_proba(transformed)[0])); v=arr[idx,0,:]
  else:
   arr=np.asarray(vals)
   if arr.ndim==3: idx=int(np.argmax(clf.predict_proba(transformed)[0])); v=arr[0,:,idx]
   elif arr.ndim==2: v=arr[0]
   else: v=arr.reshape(-1)
 except Exception:
  source='feature_importance_fallback'; v=np.asarray(clf.feature_importances_)
 v=np.asarray(v).reshape(-1); items=sorted(zip(names,v),key=lambda x:abs(float(x[1])),reverse=True)[:8]
 clean=[{'factor':str(n),'impact':round(float(v),5),'direction':'increases_risk' if float(v)>0 else 'decreases_risk'} for n,v in items]; actions=[]
 for x in clean:
  s=x['factor'].split('__')[-1].replace('_',' ')
  if any(k in s.lower() for k in ['compensation','approval','legal','documentation','rehabilitation','possession']): actions.append('Prioritize '+s)
 return {'explanation_method':source,'top_contributors':clean,'recommended_actions':actions[:5] or ['Continue routine monitoring and update pending-stage data.']}
