
import pandas as pd, numpy as np
from pathlib import Path
from .ml_service import model,FEATURES

DISPLAY_NAMES={
    "project_type":"Project type", "land_required":"Land required", "affected_parcels":"Affected parcels",
    "affected_families":"Affected families", "legal_disputes":"Legal disputes", "compensation_pending":"Compensation pending",
    "approval_pending":"Approval pending", "documentation_pending":"Documentation pending", "rehabilitation_pending":"Rehabilitation pending",
    "notification_pending":"Notification pending", "award_pending":"Award pending", "possession_pending":"Possession pending",
    "stakeholder_responsiveness":"Stakeholder responsiveness", "environmental_risk":"Environmental risk", "weather_risk":"Weather risk",
}

def explain_parcel(parcel):
    m=model()
    if m is None:
        return {"available":False,"reason":"Risk model is unavailable for this parcel."}
    features={k:parcel.get(k,0) for k in FEATURES}
    features["project_type"]=parcel.get("project_type") or "Road"
    features["land_required"]=parcel.get("land_required",parcel.get("area",0))
    X=pd.DataFrame([features])[FEATURES]
    for c in FEATURES:
        if c != "project_type": X[c]=pd.to_numeric(X[c],errors="coerce")
    X["project_type"]=X["project_type"].astype(str)
    transformed=m.named_steps["preprocessor"].transform(X)
    clf=m.named_steps["model"]
    probabilities=clf.predict_proba(transformed)[0]
    class_index=int(np.argmax(probabilities)); category=str(clf.classes_[class_index]); confidence=float(probabilities[class_index]); score=round(confidence*100,2)
    import shap
    background_source=Path(__file__).resolve().parents[2]/"data/coimbatore/18_ml_training_features.csv"
    background=pd.read_csv(background_source,nrows=100)[FEATURES].copy()
    for c in FEATURES:
        if c != "project_type": background[c]=pd.to_numeric(background[c],errors="coerce")
    background["project_type"]=background["project_type"].astype(str)
    background_transformed=m.named_steps["preprocessor"].transform(background)
    if hasattr(background_transformed,"toarray"): background_transformed=background_transformed.toarray()
    transformed_dense=transformed.toarray() if hasattr(transformed,"toarray") else transformed
    explainer=shap.TreeExplainer(clf, data=background_transformed, feature_perturbation="interventional", model_output="probability")
    raw_values=explainer.shap_values(transformed_dense)
    values=np.asarray(raw_values)
    if values.ndim == 3: contributions=values[0,:,class_index]
    elif values.ndim == 2 and values.shape[0] == len(clf.classes_): contributions=values[class_index]
    else: contributions=values.reshape(-1)
    base=np.asarray(explainer.expected_value).reshape(-1)[class_index]
    names=list(m.named_steps["preprocessor"].get_feature_names_out())
    output=[]
    for name,value in zip(names,contributions):
        raw_name=name.split("__",1)[-1]
        source_feature=raw_name
        feature_value=None
        if raw_name.startswith("project_type_"):
            source_feature="project_type"; feature_value=features["project_type"]
            display=f"Project type = {raw_name.replace('project_type_','')}"
        else:
            source_feature=raw_name; feature_value=features.get(raw_name)
            display=DISPLAY_NAMES.get(raw_name,raw_name.replace("_"," ").title())
        output.append({"name":source_feature,"display_name":display,"value":feature_value,"shap_value":round(float(value),6),"impact":"increases_risk" if float(value)>0 else "decreases_risk"})
    output.sort(key=lambda item:abs(item["shap_value"]),reverse=True)
    positive=[x for x in output if x["shap_value"]>0]
    actions=[]
    for item in positive[:5]:
        name=item["name"]
        if "compensation" in name: actions.append("Prioritize compensation review.")
        elif "legal" in name: actions.append("Review land dispute and objection records.")
        elif "verification" in name or "documentation" in name: actions.append("Prioritize field verification and missing records.")
        elif name in ("approval_pending","notification_pending","award_pending","possession_pending"): actions.append("Review milestone SLA and process bottleneck.")
    return {"available":True,"explanation_method":"SHAP TreeExplainer","output_space":"model probability for the predicted class","parcel_id":parcel["id"],"risk_score":score,"risk_category":category,"confidence":round(confidence,6),"stored_risk_category":parcel.get("risk_category"),"stored_risk_score":parcel.get("risk_score"),"stored_confidence":parcel.get("risk_probability"),"model_version":parcel.get("model_version") or "delay_risk_model.joblib","base_value":round(float(base),6),"final_value":round(float(base+sum(x["shap_value"] for x in output)),6),"features":output,"top_contributors":output[:8],"recommended_actions":list(dict.fromkeys(actions))[:3] or ["Continue routine monitoring and update verified stage data."],"model_probabilities":{str(c):round(float(p),6) for c,p in zip(clf.classes_,probabilities)}}
def explain(f):
    m=model()
    if m is None: return {"explanation_method":"unavailable","top_contributors":[],"recommended_actions":[]}
    X=pd.DataFrame([f])
    for c in FEATURES:
        if c not in X: X[c]=0 if c!="project_type" else "Road"
        if c!="project_type": X[c]=pd.to_numeric(X[c],errors="coerce")
    X["project_type"]=X["project_type"].astype(str); transformed=m.named_steps["preprocessor"].transform(X[FEATURES]); names=m.named_steps["preprocessor"].get_feature_names_out(); clf=m.named_steps["model"]
    source="SHAP"
    try:
        import shap
        vals=shap.TreeExplainer(clf).shap_values(transformed)
        probs=clf.predict_proba(transformed)[0]; idx=int(np.argmax(probs))
        arr=np.asarray(vals)
        if arr.ndim==3: v=arr[0,:,idx]
        elif arr.ndim==2 and arr.shape[0]==len(clf.classes_): v=arr[idx]
        else: v=arr.reshape(-1)
    except Exception:
        source="feature_importance_fallback"; v=np.asarray(clf.feature_importances_)
    items=sorted(zip(names,v),key=lambda x:abs(float(x[1])),reverse=True)[:8]
    clean=[{"factor":str(n).split("__")[-1].replace("_"," "),"feature":str(n),"shap_value":round(float(v),5),"direction":"increases_risk" if float(v)>0 else "decreases_risk"} for n,v in items]
    actions=[]
    for x in clean:
        s=x["factor"].lower()
        if "compensation" in s: actions.append("Verify compensation documents and prioritize payment.")
        elif "legal" in s: actions.append("Review legal case and assign resolution owner.")
        elif "documentation" in s: actions.append("Verify missing records and route for human review.")
        elif "approval" in s: actions.append("Escalate overdue approval.")
        elif "rehabilitation" in s: actions.append("Assign R&R case officer and track milestones.")
    return {"explanation_method":source,"top_contributors":clean,"recommended_actions":list(dict.fromkeys(actions))[:5] or ["Continue routine monitoring and update verified stage data."]}
