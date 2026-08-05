import os
from datetime import date

from passlib.context import CryptContext
from sqlmodel import SQLModel, Session, create_engine, select

from models import AdminUser, Block, Device, DeviceRole, RateSetting, RateType, Supplier, SystemSetting, Team

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
os.makedirs(DATA_DIR, exist_ok=True)
PHOTOS_DIR = os.path.join(DATA_DIR, "photos")
os.makedirs(PHOTOS_DIR, exist_ok=True)
DB_PATH = os.path.join(DATA_DIR, "laughing_waters.db")
DATABASE_URL = f"sqlite:///{DB_PATH}"

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Real block data currently in use on the farm - id, name, variety, tree
# count, hectares. Update this (and re-import via Master Data if the
# server's already running - see MANUAL.md chapter 8) whenever the farm's
# actual block layout changes, e.g. a block gets re-divided by variety.
REAL_BLOCKS = [
    ("7", "Block 7", "Mauritius", 2132, 15.2),
    ("8a", "Block 8a-ED", "Early Delight", 300, 2.1),
    ("8b", "Block 8b-HL", "Hung Long", 214, 1.5),
    ("9", "Block 9", "Mauritius", 383, 2.7),
    ("10a", "Block 10a-Mau", "Mauritius", 512, 2.5),
    ("10b", "Block 10b-ED", "Early Delight", 512, 2.4),
    ("11", "Block 11", "Mauritius", 434, 2.1),
    ("12", "Block 12", "Mauritius", 1064, 5.1),
    ("13", "Block 13", "Mauritius", 720, 3.5),
    ("14", "Block 14", "Third Month Red", 1064, 5.1),
    ("15", "Block 15", "Mauritius", 944, 4.5),
    ("16", "Block 16", "Third Month Red", 1064, 5.1),
    ("17a", "Block 17a-Mau", "Mauritius", 584, 2.8),
    ("17b", "Block 17b-ED", "Early Delight", 584, 2.8),
    ("18", "Block 18", "Mauritius", 770, 3.7),
    ("19a", "Block 19a-Mau", "Mauritius", 358, 1.7),
    ("19b", "Block 19b-ED", "Early Delight", 358, 1.7),
    ("22", "Block 22", "Early Delight", 210, 1.1),
    ("23", "Block 23", "Early Delight", 310, 1.6),
    ("34", "Block 34", "Early Delight", 210, 1.1),
    ("35", "Block 35", "Mix", 140, 0.7),
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
            for block_id, name, variety, trees, hectares in REAL_BLOCKS:
                session.add(Block(id=block_id, name=name, variety=variety, trees=trees, hectares=hectares))

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
