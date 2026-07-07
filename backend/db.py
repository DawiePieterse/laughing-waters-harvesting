import os
from datetime import date

from passlib.context import CryptContext
from sqlmodel import SQLModel, Session, create_engine, select

from models import AdminUser, Block, Device, DeviceRole, RateSetting, RateType, Supplier, SystemSetting, Team

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
os.makedirs(DATA_DIR, exist_ok=True)
DB_PATH = os.path.join(DATA_DIR, "laughing_waters.db")
DATABASE_URL = f"sqlite:///{DB_PATH}"

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Real block labels currently in use on the farm (Daaglikse Oesdata 2025.xlsx).
# Variety/trees/hectares are left blank for the admin to fill in via Master
# Data / CSV import - the source spreadsheet uses merged headers that are too
# fragile to auto-map per block without risking wrong tree counts.
REAL_BLOCK_LABELS = [
    "7", "8a", "8b", "9", "10", "11", "12", "13", "14", "15",
    "16", "17", "18", "19", "22", "23", "34", "35",
]

DEFAULT_ADMIN_USERNAME = "admin"
DEFAULT_ADMIN_PASSWORD = "ChangeMe123!"  # must be changed on first login


def create_db_and_tables() -> None:
    SQLModel.metadata.create_all(engine)


def get_session():
    with Session(engine) as session:
        yield session


def get_own_supplier_id(session: Session):
    """The supplier row representing the farm's own fruit - every lot
    dispatched from a field device is auto-tagged with this id."""
    own = session.exec(select(Supplier).where(Supplier.is_own_farm == True)).first()  # noqa: E712
    return own.id if own else None


def seed_defaults() -> None:
    with Session(engine) as session:
        if not session.exec(select(Team)).first():
            session.add(Team(id="A", name="Span A", induna=""))
            session.add(Team(id="B", name="Span B", induna=""))

        if not session.exec(select(Block)).first():
            for label in REAL_BLOCK_LABELS:
                session.add(Block(id=label, name=f"Block {label}"))

        if not session.exec(select(Device)).first():
            for i in range(1, 6):
                team_id = "A" if i <= 3 else "B"
                session.add(Device(id=f"device-0{i}", station=f"Field Station {i}", role=DeviceRole.field,
                                    team_id=team_id))
            session.add(Device(id="device-06", station="Packhouse Receiving 1", role=DeviceRole.packhouse))
            session.add(Device(id="device-07", station="Packhouse Receiving 2", role=DeviceRole.packhouse))
            session.add(Device(id="admin-pc", station="Pack house office", role=DeviceRole.admin))

        if not session.exec(select(RateSetting)).first():
            session.add(RateSetting(
                effective_date=date.today(),
                rate_type=RateType.per_kg,
                default_rate_per_kg=3.00,
                tier_rates_json='{"1": 2.5, "1.5": 3.5, "2": 4.5}',
            ))

        if not session.exec(select(SystemSetting)).first():
            session.add(SystemSetting())

        if not session.exec(select(Supplier).where(Supplier.is_own_farm == True)).first():  # noqa: E712
            session.add(Supplier(name="Laughing Waters (Own)", is_own_farm=True))

        if not session.exec(select(AdminUser)).first():
            session.add(AdminUser(
                username=DEFAULT_ADMIN_USERNAME,
                password_hash=pwd_context.hash(DEFAULT_ADMIN_PASSWORD),
            ))

        session.commit()
