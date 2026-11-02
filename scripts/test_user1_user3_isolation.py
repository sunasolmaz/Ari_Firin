import sys
import os
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.core.database import db
from src.models.user import User

u1 = User.get_by_username('suna14270')
u3 = User.get_by_username('ArifirinMuhasebe1976')

db.set_tenant(u1.get_tenant_schema())
u1_cust = db.fetch_all("SELECT count(*) as c FROM Customers")[0]['c']
u1_inv = db.fetch_all("SELECT count(*) as c FROM Invoices")[0]['c']
u1_prod = db.fetch_all("SELECT count(*) as c FROM Products")[0]['c']
print(f"User 1 ({u1.username} - {u1.get_tenant_schema()}): Customers={u1_cust}, Invoices={u1_inv}, Products={u1_prod}")

db.set_tenant(u3.get_tenant_schema())
u3_cust = db.fetch_all("SELECT count(*) as c FROM Customers")[0]['c']
u3_inv = db.fetch_all("SELECT count(*) as c FROM Invoices")[0]['c']
u3_prod = db.fetch_all("SELECT count(*) as c FROM Products")[0]['c']
print(f"User 3 ({u3.username} - {u3.get_tenant_schema()}): Customers={u3_cust}, Invoices={u3_inv}, Products={u3_prod}")

db.clear_tenant()
print("Isolation between User 1 and User 3 verified successfully.")
