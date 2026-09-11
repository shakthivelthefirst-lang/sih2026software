from backend.services.ml_service import train_new
from backend.core import conn
m=train_new(); c=conn(); c.execute('INSERT OR IGNORE INTO model_versions(version,model_path,training_rows,accuracy) VALUES(?,?,?,?)',(m['version'],m['version']+'.joblib',m['rows'],m['accuracy'])); c.commit(); c.close(); print(m)
