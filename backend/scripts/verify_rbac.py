from app.core.db import engine
from sqlmodel import Session, select
from app.models import User, Permission, Role

with Session(engine) as session:
    u = session.exec(select(User).where(User.is_superuser == True)).first()
    print(f"Superuser: {u.email}" if u else "No superuser")

    ps = session.exec(select(Permission)).all()
    print(f"Permissions: {len(ps)}")
    for p in ps:
        print(f"  {p.code} ({p.module})")

    rs = session.exec(select(Role)).all()
    print(f"Roles: {len(rs)}")
    for r in rs:
        print(f"  {r.name}: {len(r.permissions)} perms")
