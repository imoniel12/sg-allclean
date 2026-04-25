import os
import re
import secrets
from datetime import datetime, UTC
from pathlib import Path
from typing import Generator

from fastapi import FastAPI, Request
from fastapi.exception_handlers import http_exception_handler
from fastapi.exceptions import HTTPException
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from dotenv import load_dotenv
from sqlalchemy import DateTime, Integer, String, Text, create_engine, select, text
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.sessions import SessionMiddleware
from werkzeug.security import check_password_hash, generate_password_hash
from markupsafe import Markup, escape


BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
DEFAULT_UPLOADS_DIR = STATIC_DIR / "uploads"
FAVICON_DIR = BASE_DIR / "favicon"
load_dotenv(BASE_DIR / ".env")


def normalize_database_url(value: str | None) -> str:
    raw = str(value or "").strip()
    if not raw:
        return f"sqlite:///{BASE_DIR / 'sg_allclean.db'}"
    if raw.startswith("postgres://"):
        return "postgresql+psycopg://" + raw[len("postgres://"):]
    if raw.startswith("postgresql://"):
        return "postgresql+psycopg://" + raw[len("postgresql://"):]
    return raw


DATABASE_URL = normalize_database_url(os.environ.get("DATABASE_URL"))


def resolve_uploads_dir() -> Path:
    configured = str(os.environ.get("UPLOADS_DIR", "")).strip()
    if configured:
        return Path(configured).expanduser()
    return DEFAULT_UPLOADS_DIR


UPLOADS_DIR = resolve_uploads_dir()
LOGOS_DIR = UPLOADS_DIR / "logos"
POSTS_DIR = UPLOADS_DIR / "posts"


def normalize_admin_base_path(value: str) -> str:
    cleaned = "/" + str(value or "/portal-access").strip().strip("/")
    return cleaned.rstrip("/") or "/portal-access"


ADMIN_BASE_PATH = normalize_admin_base_path(os.environ.get("ADMIN_BASE_PATH", "/portal-access"))
FULL_ADMIN_ROLE = "full_admin"
CONTENT_MODERATOR_ROLE = "content_moderator"


class Base(DeclarativeBase):
    pass


IS_SQLITE = DATABASE_URL.startswith("sqlite")
engine_kwargs = {"pool_pre_ping": True}
if IS_SQLITE:
    engine_kwargs["connect_args"] = {"check_same_thread": False}
engine = create_engine(DATABASE_URL, **engine_kwargs)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


class AdminUser(Base):
    __tablename__ = "admin_user"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(40), nullable=False, default=FULL_ADMIN_ROLE)
    is_active: Mapped[str] = mapped_column(String(5), nullable=False, default="true")


class SiteSettings(Base):
    __tablename__ = "site_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_name: Mapped[str] = mapped_column(String(140), nullable=False)
    tagline: Mapped[str] = mapped_column(String(220), nullable=False)
    hero_title: Mapped[str] = mapped_column(String(220), nullable=False)
    hero_subtitle: Mapped[str] = mapped_column(Text, nullable=False)
    intro_title: Mapped[str] = mapped_column(String(220), nullable=False)
    intro_body: Mapped[str] = mapped_column(Text, nullable=False)
    contact_email: Mapped[str] = mapped_column(String(140), nullable=False)
    contact_phone: Mapped[str] = mapped_column(String(80), nullable=False)
    location: Mapped[str] = mapped_column(String(140), nullable=False)
    coverage: Mapped[str] = mapped_column(String(220), nullable=False)
    investment_note: Mapped[str] = mapped_column(Text, nullable=False)
    logo_path: Mapped[str] = mapped_column(String(240), nullable=False, default="")


class Page(Base):
    __tablename__ = "page"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    slug: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)
    title: Mapped[str] = mapped_column(String(180), nullable=False)
    subtitle: Mapped[str] = mapped_column(String(220), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    cta_text: Mapped[str] = mapped_column(String(80), nullable=False, default="")
    cta_link: Mapped[str] = mapped_column(String(180), nullable=False, default="")


class Service(Base):
    __tablename__ = "service"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(180), nullable=False)
    slug: Mapped[str] = mapped_column(String(180), unique=True, nullable=False)
    summary: Mapped[str] = mapped_column(String(280), nullable=False)
    details: Mapped[str] = mapped_column(Text, nullable=False)
    highlight: Mapped[str] = mapped_column(String(120), nullable=False, default="")
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class Post(Base):
    __tablename__ = "post"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    slug: Mapped[str] = mapped_column(String(200), unique=True, nullable=False)
    excerpt: Mapped[str] = mapped_column(String(320), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    image_path: Mapped[str] = mapped_column(String(240), nullable=False, default="")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="draft")
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )


class ContactField(Base):
    __tablename__ = "contact_field"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    label: Mapped[str] = mapped_column(String(120), nullable=False)
    name: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    field_type: Mapped[str] = mapped_column(String(40), nullable=False, default="text")
    placeholder: Mapped[str] = mapped_column(String(180), nullable=False, default="")
    options: Mapped[str] = mapped_column(Text, nullable=False, default="")
    required: Mapped[str] = mapped_column(String(5), nullable=False, default="true")
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_active: Mapped[str] = mapped_column(String(5), nullable=False, default="true")


class NavItem(Base):
    __tablename__ = "nav_item"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    label: Mapped[str] = mapped_column(String(120), nullable=False)
    path: Mapped[str] = mapped_column(String(180), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_button: Mapped[str] = mapped_column(String(5), nullable=False, default="false")
    is_active: Mapped[str] = mapped_column(String(5), nullable=False, default="true")


class ContentSnippet(Base):
    __tablename__ = "content_snippet"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    key: Mapped[str] = mapped_column(String(160), unique=True, nullable=False)
    label: Mapped[str] = mapped_column(String(180), nullable=False)
    value: Mapped[str] = mapped_column(Text, nullable=False, default="")
    group_name: Mapped[str] = mapped_column(String(80), nullable=False, default="homepage")
    input_type: Mapped[str] = mapped_column(String(30), nullable=False, default="textarea")
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


def slugify(value: str) -> str:
    value = re.sub(r"[^a-zA-Z0-9\s-]", "", value or "").strip().lower()
    return re.sub(r"[-\s]+", "-", value).strip("-") or "untitled"


def render_rich_text(value: str) -> Markup:
    if not value:
        return Markup("")
    paragraphs = []
    for block in value.strip().split("\n\n"):
        lines = "<br>".join(escape(line.strip()) for line in block.splitlines() if line.strip())
        if lines:
            paragraphs.append(f"<p>{lines}</p>")
    return Markup("".join(paragraphs))


def db_session() -> Generator[Session, None, None]:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def admin_path(path: str = "") -> str:
    clean_path = str(path or "").strip()
    if not clean_path:
        return ADMIN_BASE_PATH
    return f"{ADMIN_BASE_PATH}/" + clean_path.lstrip("/")


def is_admin(request: Request) -> bool:
    return bool(request.session.get("admin_user_id"))


def get_current_admin_user(session: Session, request: Request) -> AdminUser | None:
    user_id = request.session.get("admin_user_id")
    if not user_id:
        return None
    return session.get(AdminUser, user_id)


def has_role(user: AdminUser | None, *roles: str) -> bool:
    return bool(user and user.is_active == "true" and user.role in roles)


def require_admin_user(request: Request, session: Session) -> AdminUser | RedirectResponse:
    user = get_current_admin_user(session, request)
    if not user or user.is_active != "true":
        request.session.clear()
        flash(request, "error", "Please sign in with an active admin account.")
        return redirect_to(admin_path("/login"))
    return user


def require_full_admin(request: Request, session: Session) -> AdminUser | RedirectResponse:
    user = require_admin_user(request, session)
    if isinstance(user, RedirectResponse):
        return user
    if user.role != FULL_ADMIN_ROLE:
        flash(request, "error", "Full admin access is required for that section.")
        return redirect_to(admin_path())
    return user


def flash(request: Request, category: str, message: str) -> None:
    messages = request.session.get("_flash_messages", [])
    messages.append({"category": category, "message": message})
    request.session["_flash_messages"] = messages


def pop_flashes(request: Request) -> list[dict[str, str]]:
    messages = request.session.get("_flash_messages", [])
    request.session["_flash_messages"] = []
    return messages


def get_settings(session: Session) -> SiteSettings | None:
    return session.scalar(select(SiteSettings).limit(1))


def template_context(request: Request, session: Session, **extra):
    is_admin_area = request.url.path.startswith(ADMIN_BASE_PATH)
    nav_items = []
    footer = {}
    current_admin_user = get_current_admin_user(session, request) if is_admin_area else None
    if not is_admin_area:
        nav_items = session.scalars(
            select(NavItem).where(NavItem.is_active == "true").order_by(NavItem.sort_order.asc())
        ).all()
    footer = get_snippet_map(session, "footer")
    context = {
        "request": request,
        "site_settings": get_settings(session),
        "messages": pop_flashes(request),
        "current_path": request.url.path,
        "is_admin_area": is_admin_area,
        "nav_items": nav_items,
        "footer_content": footer,
        "current_admin_user": current_admin_user,
        "admin_base_path": ADMIN_BASE_PATH,
        "full_admin_role": FULL_ADMIN_ROLE,
        "content_moderator_role": CONTENT_MODERATOR_ROLE,
    }
    context.update(extra)
    return context


def get_snippet_map(session: Session, group_name: str = "homepage") -> dict[str, str]:
    snippets = session.scalars(
        select(ContentSnippet).where(ContentSnippet.group_name == group_name).order_by(ContentSnippet.sort_order.asc())
    ).all()
    return {snippet.key: snippet.value for snippet in snippets}


def secure_upload_name(filename: str) -> str:
    suffix = Path(filename or "").suffix.lower()
    if suffix not in {".png", ".jpg", ".jpeg", ".svg", ".webp"}:
        return ""
    stem = slugify(Path(filename).stem)[:50]
    token = secrets.token_hex(8)
    return f"{stem or 'logo'}-{token}{suffix}"


def redirect_to(path: str, status_code: int = 303) -> RedirectResponse:
    return RedirectResponse(url=path, status_code=status_code)


def full_admin_count(session: Session) -> int:
    return len(
        session.scalars(
            select(AdminUser).where(AdminUser.role == FULL_ADMIN_ROLE, AdminUser.is_active == "true")
        ).all()
    )


def seed_database() -> None:
    with SessionLocal() as session:
        if not session.scalar(select(AdminUser).limit(1)):
            session.add(
                AdminUser(
                    username="admin",
                    password_hash=generate_password_hash(
                        os.environ.get("ADMIN_PASSWORD", "admin123")
                    ),
                    role=FULL_ADMIN_ROLE,
                    is_active="true",
                )
            )
        else:
            users = session.scalars(select(AdminUser)).all()
            for user in users:
                if not user.role:
                    user.role = FULL_ADMIN_ROLE
                if not user.is_active:
                    user.is_active = "true"

        if not session.scalar(select(SiteSettings).limit(1)):
            session.add(
                SiteSettings(
                    company_name="SG AllClean Environmental Services",
                    tagline="Clean spaces. Clear minds. Better living.",
                    hero_title="Hotel-grade cleaning for modern city living.",
                    hero_subtitle=(
                        "SG AllClean delivers premium property care for condos, offices, "
                        "Airbnb units, and fast-moving urban spaces across Makati, BGC, and Ortigas."
                    ),
                    intro_title="A premium cleaning brand built for recurring trust.",
                    intro_body=(
                        "We serve busy professionals, property owners, expats, and operators who need "
                        "reliable housekeeping, deep cleaning, turnover support, and detail-focused teams "
                        "that show up consistently."
                    ),
                    contact_email="bantomagrace@gmail.com",
                    contact_phone="+63-995 457 3462",
                    location="Makati",
                    coverage="Makati, BGC, Ortigas, and nearby premium residential and commercial districts",
                    investment_note=(
                        "The proposal positions SG AllClean as a premium, recurring-revenue service brand "
                        "with strong demand from condos, Airbnb hosts, and modern urban households."
                    ),
                    logo_path="",
                )
            )

        if not session.scalar(select(Page).limit(1)):
            session.add_all(
                [
                    Page(
                        slug="about",
                        title="Professional care with a lifestyle-brand mindset.",
                        subtitle="A detail-led team for homes, workplaces, and revenue-generating properties.",
                        body=(
                            "SG AllClean Environmental Services was built around one simple idea: "
                            "cleaning should feel dependable, polished, and quietly excellent.\n\n"
                            "Our service model focuses on trained staff, safe cleaning materials, "
                            "structured quality standards, and a premium client experience from booking "
                            "through completion.\n\n"
                            "We work with condo owners, Airbnb hosts, expats, professionals, and small "
                            "office teams who value consistency, presentation, and peace of mind."
                        ),
                        cta_text="View Services",
                        cta_link="/services",
                    ),
                    Page(
                        slug="contact",
                        title="Let’s plan a cleaner, calmer space.",
                        subtitle="Tell us what needs attention and we’ll match the right service approach.",
                        body=(
                            "Whether you need routine housekeeping, office support, deep cleaning, or "
                            "same-day turnover readiness, we can shape a package around your schedule.\n\n"
                            "Use the contact details below to request a schedule, ask for a custom package, "
                            "or coordinate a recurring service plan for your property."
                        ),
                        cta_text="Contact Us",
                        cta_link="/contact",
                    ),
                    Page(
                        slug="privacy",
                        title="Data Privacy Statement",
                        subtitle="How SG AllClean Environmental Services handles personal information in connection with inquiries, bookings, and customer communication.",
                        body=(
                            "SG AllClean Environmental Services values your privacy and handles personal information in a responsible, secure, and lawful manner.\n\n"
                            "We collect only the information reasonably needed to respond to inquiries, arrange services, manage bookings, and support our client relationship.\n\n"
                            "Depending on your interaction with us, we may collect your name, company name, address details, phone number, email address, service location, inquiry notes, booking preferences, and other information reasonably needed to deliver our cleaning services or respond to your request.\n\n"
                            "We collect information directly from you when you submit an inquiry, contact us by email or phone, request a quotation, book a service, give feedback, or otherwise communicate with our team.\n\n"
                            "We process personal data to evaluate and respond to inquiries, coordinate schedules, confirm service requirements, manage customer records, improve service quality, send updates related to bookings, handle billing or business documentation where applicable, and comply with legal or regulatory obligations.\n\n"
                            "We may share your information only when reasonably necessary with staff, service coordinators, contractors, technology providers, payment or business support providers, and government or legal authorities when required by law.\n\n"
                            "We retain personal data only for as long as it is reasonably necessary for inquiry handling, service delivery, customer care, record-keeping, dispute management, security, or compliance with applicable laws and internal operational requirements.\n\n"
                            "We use reasonable organizational, technical, and physical safeguards to protect personal information against unauthorized access, improper disclosure, loss, misuse, or unlawful alteration.\n\n"
                            "Subject to applicable law, you may request access to your personal data, ask for corrections, object to certain processing, request deletion or restriction where appropriate, withdraw consent when consent is the basis for processing, or raise a concern about how your information is handled.\n\n"
                            "For privacy-related questions or requests, please contact SG AllClean Environmental Services through the email and phone details published on this website."
                        ),
                        cta_text="Contact Us",
                        cta_link="/contact",
                    ),
                ]
            )
        else:
            contact_page = session.scalar(select(Page).where(Page.slug == "contact"))
            if contact_page and contact_page.cta_link in {admin_path("/login"), "mailto:bantomagrace@gmail.com"}:
                contact_page.cta_text = "Contact Us"
                contact_page.cta_link = "/contact"
                contact_page.body = (
                    "Whether you need routine housekeeping, office support, deep cleaning, or "
                    "same-day turnover readiness, we can shape a package around your schedule.\n\n"
                    "Use the contact details below to request a schedule, ask for a custom package, "
                    "or coordinate a recurring service plan for your property."
                )
            privacy_page = session.scalar(select(Page).where(Page.slug == "privacy"))
            if not privacy_page:
                session.add(
                    Page(
                        slug="privacy",
                        title="Data Privacy Statement",
                        subtitle="How SG AllClean Environmental Services handles personal information in connection with inquiries, bookings, and customer communication.",
                        body=(
                            "SG AllClean Environmental Services values your privacy and handles personal information in a responsible, secure, and lawful manner.\n\n"
                            "We collect only the information reasonably needed to respond to inquiries, arrange services, manage bookings, and support our client relationship.\n\n"
                            "Depending on your interaction with us, we may collect your name, company name, address details, phone number, email address, service location, inquiry notes, booking preferences, and other information reasonably needed to deliver our cleaning services or respond to your request.\n\n"
                            "We collect information directly from you when you submit an inquiry, contact us by email or phone, request a quotation, book a service, give feedback, or otherwise communicate with our team.\n\n"
                            "We process personal data to evaluate and respond to inquiries, coordinate schedules, confirm service requirements, manage customer records, improve service quality, send updates related to bookings, handle billing or business documentation where applicable, and comply with legal or regulatory obligations.\n\n"
                            "We may share your information only when reasonably necessary with staff, service coordinators, contractors, technology providers, payment or business support providers, and government or legal authorities when required by law.\n\n"
                            "We retain personal data only for as long as it is reasonably necessary for inquiry handling, service delivery, customer care, record-keeping, dispute management, security, or compliance with applicable laws and internal operational requirements.\n\n"
                            "We use reasonable organizational, technical, and physical safeguards to protect personal information against unauthorized access, improper disclosure, loss, misuse, or unlawful alteration.\n\n"
                            "Subject to applicable law, you may request access to your personal data, ask for corrections, object to certain processing, request deletion or restriction where appropriate, withdraw consent when consent is the basis for processing, or raise a concern about how your information is handled.\n\n"
                            "For privacy-related questions or requests, please contact SG AllClean Environmental Services through the email and phone details published on this website."
                        ),
                        cta_text="Contact Us",
                        cta_link="/contact",
                    )
                )

        if not session.scalar(select(Service).limit(1)):
            session.add_all(
                [
                    Service(
                        title="Residential Cleaning",
                        slug="residential-cleaning",
                        summary="Routine housekeeping and deep cleaning for premium urban homes.",
                        details=(
                            "Built for condo owners, families, and professionals who want a spotless home without "
                            "the friction of unreliable scheduling.\n\n"
                            "Includes daily or weekly upkeep, kitchen and bathroom deep cleaning, upholstery "
                            "attention, and move-in or move-out support."
                        ),
                        highlight="Premium homes",
                        sort_order=1,
                    ),
                    Service(
                        title="Corporate Cleaning",
                        slug="corporate-cleaning",
                        summary="Structured cleaning programs for offices and commercial spaces.",
                        details=(
                            "We help maintain productive environments through dependable scheduled cleaning, "
                            "post-construction cleanups, and disinfection services.\n\n"
                            "Ideal for small offices, client-facing workspaces, and growing teams that need "
                            "professional presentation every day."
                        ),
                        highlight="Office-ready",
                        sort_order=2,
                    ),
                    Service(
                        title="Airbnb and Leasing Turnovers",
                        slug="airbnb-leasing-turnovers",
                        summary="Fast, presentation-focused turnovers for hosting and leasing operations.",
                        details=(
                            "Designed for high-margin short-stay units and rental properties that depend on speed, "
                            "readiness, and guest confidence.\n\n"
                            "Includes turnover cleaning, linen and restocking coordination, and property staging support."
                        ),
                        highlight="High-margin support",
                        sort_order=3,
                    ),
                ]
            )

        if not session.scalar(select(Post).limit(1)):
            session.add_all(
                [
                    Post(
                        title="Why Premium Cleaning Wins in Urban Properties",
                        slug="why-premium-cleaning-wins-in-urban-properties",
                        excerpt="Premium clients are not looking for the cheapest cleaner. They want reliability, presentation, and trust.",
                        body=(
                            "Makati, BGC, and Ortigas continue to reward service businesses that remove friction from fast-paced city living.\n\n"
                            "For property owners and professionals, the value is not just a clean room. It is saved time, smoother turnovers, "
                            "better tenant and guest impressions, and confidence that standards will be met without chasing follow-ups.\n\n"
                            "That is where SG AllClean is positioned: premium, recurring, and detail-led."
                        ),
                        image_path="",
                        status="published",
                        published_at=datetime.now(UTC),
                    ),
                    Post(
                        title="The Real Advantage of Turnover-Ready Airbnb Cleaning",
                        slug="the-real-advantage-of-turnover-ready-airbnb-cleaning",
                        excerpt="Speed matters, but consistency is what protects reviews and repeat bookings.",
                        body=(
                            "Airbnb operators need more than a basic clean. They need a process that supports readiness between bookings.\n\n"
                            "Turnover support should protect visual presentation, restocking accuracy, and guest confidence from the first glance.\n\n"
                            "A premium turnover partner helps transform cleaning from a chore into an operational advantage."
                        ),
                        image_path="",
                        status="draft",
                    ),
                ]
            )

        if not session.scalar(select(ContactField).limit(1)):
            session.add_all(
                [
                    ContactField(label="Identification", name="identification", field_type="radio", options="Individual\nCorporation\nPartner", required="true", sort_order=1),
                    ContactField(label="First Name", name="first_name", field_type="text", placeholder="First name", required="true", sort_order=2),
                    ContactField(label="Last Name", name="last_name", field_type="text", placeholder="Last name", required="true", sort_order=3),
                    ContactField(label="Company Name", name="company_name", field_type="text", placeholder="Company name", required="false", sort_order=4),
                    ContactField(label="Postal Code", name="postal_code", field_type="text", placeholder="Postal code", required="false", sort_order=5),
                    ContactField(label="Telephone Number", name="telephone", field_type="text", placeholder="Phone number", required="true", sort_order=6),
                    ContactField(label="Email Address", name="email", field_type="email", placeholder="Email address", required="true", sort_order=7),
                    ContactField(label="Remarks or Comments", name="remarks", field_type="textarea", placeholder="Tell us about your property, schedule, and service needs", required="true", sort_order=8),
                ]
            )

        if not session.scalar(select(NavItem).limit(1)):
            session.add_all(
                [
                    NavItem(label="Home", path="/", sort_order=1, is_button="false", is_active="true"),
                    NavItem(label="About", path="/about", sort_order=2, is_button="false", is_active="true"),
                    NavItem(label="Services", path="/services", sort_order=3, is_button="false", is_active="true"),
                    NavItem(label="Journal", path="/journal", sort_order=4, is_button="false", is_active="true"),
                    NavItem(label="Contact", path="/contact", sort_order=5, is_button="false", is_active="true"),
                    NavItem(label="Get Quote", path="/contact", sort_order=6, is_button="true", is_active="true"),
                ]
            )

        if not session.scalar(select(ContentSnippet).limit(1)):
            session.add_all(
                [
                    ContentSnippet(key="home.hero_badge", label="Hero Badge", value="Premium Housekeeping", input_type="text", sort_order=1),
                    ContentSnippet(key="home.feature_1_title", label="Feature 1 Title", value="Condo-ready", input_type="text", sort_order=2),
                    ContentSnippet(key="home.feature_1_body", label="Feature 1 Body", value="For Makati, BGC, Ortigas, and premium urban residences.", sort_order=3),
                    ContentSnippet(key="home.feature_2_title", label="Feature 2 Title", value="Turnover-fast", input_type="text", sort_order=4),
                    ContentSnippet(key="home.feature_2_body", label="Feature 2 Body", value="Built for Airbnb schedules, leasing prep, and office resets.", sort_order=5),
                    ContentSnippet(key="home.feature_3_title", label="Feature 3 Title", value="Trust-led", input_type="text", sort_order=6),
                    ContentSnippet(key="home.feature_3_body", label="Feature 3 Body", value="Professional staff, consistent standards, and premium presentation.", sort_order=7),
                    ContentSnippet(key="home.notifications_title", label="Notifications Title", value="What's new at AllClean", input_type="text", sort_order=8),
                    ContentSnippet(key="home.metric_1_value", label="Metric 1 Value", value="47%", input_type="text", sort_order=9),
                    ContentSnippet(key="home.metric_1_label", label="Metric 1 Label", value="margin outlook", input_type="text", sort_order=10),
                    ContentSnippet(key="home.metric_2_value", label="Metric 2 Value", value="3", input_type="text", sort_order=11),
                    ContentSnippet(key="home.metric_2_label", label="Metric 2 Label", value="service lines", input_type="text", sort_order=12),
                    ContentSnippet(key="home.metric_3_value", label="Metric 3 Value", value="Hotel", input_type="text", sort_order=13),
                    ContentSnippet(key="home.metric_3_label", label="Metric 3 Label", value="quality feel", input_type="text", sort_order=14),
                    ContentSnippet(key="home.metric_4_value", label="Metric 4 Value", value="Fast", input_type="text", sort_order=15),
                    ContentSnippet(key="home.metric_4_label", label="Metric 4 Label", value="booking flow", input_type="text", sort_order=16),
                    ContentSnippet(key="home.notice_1_label", label="Notice 1 Label", value="Service Update", input_type="text", sort_order=17),
                    ContentSnippet(key="home.notice_1_body", label="Notice 1 Body", value="Now offering premium turnover cleaning for Airbnb and leasing-ready units.", sort_order=18),
                    ContentSnippet(key="home.notice_1_tag", label="Notice 1 Tag", value="New", input_type="text", sort_order=19),
                    ContentSnippet(key="home.notice_2_label", label="Notice 2 Label", value="Brand Focus", input_type="text", sort_order=20),
                    ContentSnippet(key="home.notice_2_body", label="Notice 2 Body", value="Refined for modern city living, recurring support, and presentation-first care.", sort_order=21),
                    ContentSnippet(key="home.notice_2_tag", label="Notice 2 Tag", value="Current", input_type="text", sort_order=22),
                    ContentSnippet(key="home.top_picks_title", label="Top Picks Title", value="Quick ways to understand what makes AllClean different.", input_type="text", sort_order=23),
                    ContentSnippet(key="home.top_picks_link", label="Top Picks Link Label", value="About the brand", input_type="text", sort_order=24),
                    ContentSnippet(key="home.pick_1_title", label="Pick 1 Title", value="Why AllClean", input_type="text", sort_order=25),
                    ContentSnippet(key="home.pick_1_body", label="Pick 1 Body", value="A premium cleaning experience designed for peace of mind, not just task completion.", sort_order=26),
                    ContentSnippet(key="home.pick_2_title", label="Pick 2 Title", value="Services", input_type="text", sort_order=27),
                    ContentSnippet(key="home.pick_2_body", label="Pick 2 Body", value="Residential, office, and turnover support shaped around city schedules and high standards.", sort_order=28),
                    ContentSnippet(key="home.pick_3_title", label="Pick 3 Title", value="Journal", input_type="text", sort_order=29),
                    ContentSnippet(key="home.pick_3_body", label="Pick 3 Body", value="Brand stories, care tips, and updates that make the service feel more transparent and human.", sort_order=30),
                    ContentSnippet(key="home.pick_4_title", label="Pick 4 Title", value="Contact", input_type="text", sort_order=31),
                    ContentSnippet(key="home.pick_4_body", label="Pick 4 Body", value="Start with a conversation about your property, frequency, and service expectations.", sort_order=32),
                    ContentSnippet(key="home.whats_title", label="What's AllClean Title", value="What's AllClean?", input_type="text", sort_order=33),
                    ContentSnippet(key="home.reasons_title", label="Reasons Title", value="Why clients choose AllClean for recurring, detail-led property care.", input_type="text", sort_order=34),
                    ContentSnippet(key="home.reason_1_title", label="Reason 1 Title", value="Trained, presentation-first teams", input_type="text", sort_order=35),
                    ContentSnippet(key="home.reason_1_body", label="Reason 1 Body", value="We are built around professionalism, safe materials, dependable routines, and cleaner finishes that hold up to premium client expectations.", sort_order=36),
                    ContentSnippet(key="home.reason_2_title", label="Reason 2 Title", value="Designed for modern urban schedules", input_type="text", sort_order=37),
                    ContentSnippet(key="home.reason_2_body", label="Reason 2 Body", value="From condos and offices to Airbnb turnovers, we shape service around real occupancy patterns, guest deadlines, and repeat bookings.", sort_order=38),
                    ContentSnippet(key="home.reason_3_title", label="Reason 3 Title", value="A trustworthy recurring model", input_type="text", sort_order=39),
                    ContentSnippet(key="home.reason_3_body", label="Reason 3 Body", value="Clients are not just buying cleaning. They are buying time back, consistency, smoother turnovers, and confidence that standards will be met.", sort_order=40),
                    ContentSnippet(key="home.services_title", label="Services Section Title", value="Core offerings for homes, offices, and booking-ready spaces.", input_type="text", sort_order=41),
                    ContentSnippet(key="home.services_link", label="Services Link Label", value="View all services", input_type="text", sort_order=42),
                    ContentSnippet(key="home.safe_title", label="Safe Section Title", value="Cleaner spaces should also feel professionally handled from start to finish.", input_type="text", sort_order=43),
                    ContentSnippet(key="home.safe_1_title", label="Safe Card 1 Title", value="Privacy, professionalism, and care", input_type="text", sort_order=44),
                    ContentSnippet(key="home.safe_1_body", label="Safe Card 1 Body", value="We aim for a calm client experience with dependable communication, careful handling of property spaces, and a service tone that feels polished and trustworthy.", sort_order=45),
                    ContentSnippet(key="home.safe_2_title", label="Safe Card 2 Title", value="Healthy-space mindset", input_type="text", sort_order=46),
                    ContentSnippet(key="home.safe_2_body", label="Safe Card 2 Body", value="Clean materials, sanitary routines, and attention to high-touch areas help create safer environments for homes, offices, guests, and teams.", sort_order=47),
                    ContentSnippet(key="home.journal_title", label="Journal Section Title", value="Updates and useful content that support trust around the service.", input_type="text", sort_order=48),
                    ContentSnippet(key="home.journal_link", label="Journal Link Label", value="Open journal", input_type="text", sort_order=49),
                    ContentSnippet(key="home.cta_badge", label="Bottom CTA Badge", value="Contact Us", input_type="text", sort_order=50),
                    ContentSnippet(key="home.cta_title", label="Bottom CTA Title", value="Tell us about your property and we'll shape the right cleaning routine.", input_type="text", sort_order=51),
                    ContentSnippet(key="home.cta_body", label="Bottom CTA Body", value="Residential cleaning, office maintenance, and Airbnb turnover support across your preferred service areas.", sort_order=52),
                    ContentSnippet(key="home.cta_primary", label="Bottom CTA Primary Button", value="Contact Us", input_type="text", sort_order=53),
                    ContentSnippet(key="home.cta_secondary", label="Bottom CTA Secondary Button", value="Email Us", input_type="text", sort_order=54),
                    ContentSnippet(key="footer.badge", label="Footer Badge", value="Premium Property Care", group_name="footer", input_type="text", sort_order=1),
                    ContentSnippet(key="footer.body", label="Footer Body", value="Reliable cleaning for city homes, offices, and high-turnover properties with a calm, polished client experience.", group_name="footer", sort_order=2),
                    ContentSnippet(key="footer.coverage_title", label="Footer Coverage Title", value="Coverage", group_name="footer", input_type="text", sort_order=3),
                    ContentSnippet(key="footer.contact_title", label="Footer Contact Title", value="Contact", group_name="footer", input_type="text", sort_order=4),
                    ContentSnippet(key="footer.policies_title", label="Footer Policies Title", value="Policies", group_name="footer", input_type="text", sort_order=5),
                    ContentSnippet(key="footer.privacy_label", label="Footer Privacy Label", value="Data Privacy Statement", group_name="footer", input_type="text", sort_order=6),
                ]
            )
        else:
            existing_keys = {
                row[0] for row in session.execute(select(ContentSnippet.key)).all()
            }
            footer_defaults = [
                ("footer.badge", "Footer Badge", "Premium Property Care", "text", 1),
                ("footer.body", "Footer Body", "Reliable cleaning for city homes, offices, and high-turnover properties with a calm, polished client experience.", "textarea", 2),
                ("footer.coverage_title", "Footer Coverage Title", "Coverage", "text", 3),
                ("footer.contact_title", "Footer Contact Title", "Contact", "text", 4),
                ("footer.policies_title", "Footer Policies Title", "Policies", "text", 5),
                ("footer.privacy_label", "Footer Privacy Label", "Data Privacy Statement", "text", 6),
            ]
            homepage_metric_defaults = [
                ("home.metric_1_value", "Metric 1 Value", "47%", "text", 9),
                ("home.metric_1_label", "Metric 1 Label", "margin outlook", "text", 10),
                ("home.metric_2_value", "Metric 2 Value", "3", "text", 11),
                ("home.metric_2_label", "Metric 2 Label", "service lines", "text", 12),
                ("home.metric_3_value", "Metric 3 Value", "Hotel", "text", 13),
                ("home.metric_3_label", "Metric 3 Label", "quality feel", "text", 14),
                ("home.metric_4_value", "Metric 4 Value", "Fast", "text", 15),
                ("home.metric_4_label", "Metric 4 Label", "booking flow", "text", 16),
            ]
            for key, label, value, input_type, sort_order in footer_defaults:
                if key not in existing_keys:
                    session.add(
                        ContentSnippet(
                            key=key,
                            label=label,
                            value=value,
                            group_name="footer",
                            input_type=input_type,
                            sort_order=sort_order,
                        )
                    )
            for key, label, value, input_type, sort_order in homepage_metric_defaults:
                if key not in existing_keys:
                    session.add(
                        ContentSnippet(
                            key=key,
                            label=label,
                            value=value,
                            group_name="homepage",
                            input_type=input_type,
                            sort_order=sort_order,
                        )
                    )

        session.commit()


def ensure_database_schema() -> None:
    if not IS_SQLITE:
        return
    with engine.begin() as connection:
        admin_columns = {
            row[1]
            for row in connection.execute(text("PRAGMA table_info(admin_user)")).fetchall()
        }
        if "role" not in admin_columns:
            connection.execute(
                text(f"ALTER TABLE admin_user ADD COLUMN role VARCHAR(40) NOT NULL DEFAULT '{FULL_ADMIN_ROLE}'")
            )
        if "is_active" not in admin_columns:
            connection.execute(
                text("ALTER TABLE admin_user ADD COLUMN is_active VARCHAR(5) NOT NULL DEFAULT 'true'")
            )
        columns = {
            row[1]
            for row in connection.execute(text("PRAGMA table_info(site_settings)")).fetchall()
        }
        if "logo_path" not in columns:
            connection.execute(
                text("ALTER TABLE site_settings ADD COLUMN logo_path VARCHAR(240) NOT NULL DEFAULT ''")
            )
        post_columns = {
            row[1]
            for row in connection.execute(text("PRAGMA table_info(post)")).fetchall()
        }
        if "image_path" not in post_columns:
            connection.execute(
                text("ALTER TABLE post ADD COLUMN image_path VARCHAR(240) NOT NULL DEFAULT ''")
            )


app = FastAPI(
    title="SG AllClean CMS",
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)
app.add_middleware(
    SessionMiddleware,
    secret_key=os.environ.get("SECRET_KEY", "sg-allclean-dev-secret"),
    same_site="lax",
    https_only=os.environ.get("SESSION_HTTPS_ONLY", "false").lower() == "true",
)
app.mount("/static/uploads", StaticFiles(directory=UPLOADS_DIR, check_dir=False), name="uploads")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
app.mount("/favicon", StaticFiles(directory=FAVICON_DIR), name="favicon")

templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))
templates.env.filters["richtext"] = render_rich_text


@app.on_event("startup")
def startup_event():
    LOGOS_DIR.mkdir(parents=True, exist_ok=True)
    POSTS_DIR.mkdir(parents=True, exist_ok=True)
    Base.metadata.create_all(bind=engine)
    ensure_database_schema()
    seed_database()


@app.exception_handler(HTTPException)
@app.exception_handler(StarletteHTTPException)
async def branded_http_exception_handler(request: Request, exc: HTTPException | StarletteHTTPException):
    if exc.status_code != 404:
        return await http_exception_handler(request, exc)
    with SessionLocal() as session:
        return templates.TemplateResponse(
            "404.html",
            template_context(request, session, missing_path=request.url.path),
            status_code=404,
        )


@app.get("/", name="index")
def index(request: Request):
    with SessionLocal() as session:
        settings = get_settings(session)
        services = session.scalars(select(Service).order_by(Service.sort_order.asc())).all()
        posts = session.scalars(
            select(Post).where(Post.status == "published").order_by(Post.published_at.desc()).limit(3)
        ).all()
        homepage = get_snippet_map(session, "homepage")
        return templates.TemplateResponse(
            "index.html",
            template_context(request, session, settings=settings, services=services, posts=posts, homepage=homepage),
        )


@app.get("/favicon.ico", include_in_schema=False)
def favicon_ico():
    return FileResponse(FAVICON_DIR / "favicon.ico")


@app.get("/about", name="about")
def about(request: Request):
    with SessionLocal() as session:
        page = session.scalar(select(Page).where(Page.slug == "about"))
        return templates.TemplateResponse("page.html", template_context(request, session, page=page))


@app.get("/contact", name="contact")
def contact(request: Request):
    with SessionLocal() as session:
        page = session.scalar(select(Page).where(Page.slug == "contact"))
        form_fields = session.scalars(
            select(ContactField).where(ContactField.is_active == "true").order_by(ContactField.sort_order.asc())
        ).all()
        return templates.TemplateResponse("contact.html", template_context(request, session, page=page, form_fields=form_fields))


@app.post("/contact", name="contact_submit")
async def contact_submit(request: Request):
    form = await request.form()
    consent = str(form.get("privacy_consent", "")).lower()
    if consent not in {"on", "true", "1", "yes"}:
        flash(request, "error", "Please agree to the Data Privacy Statement before submitting your inquiry.")
        return redirect_to("/contact")
    flash(request, "success", "Your inquiry details are ready. You can now continue through your preferred contact channel.")
    return redirect_to("/contact")


@app.get("/privacy", name="privacy")
def privacy(request: Request):
    with SessionLocal() as session:
        page = session.scalar(select(Page).where(Page.slug == "privacy"))
        return templates.TemplateResponse("privacy.html", template_context(request, session, page=page))


@app.get("/services", name="services")
def services(request: Request):
    with SessionLocal() as session:
        services_list = session.scalars(select(Service).order_by(Service.sort_order.asc())).all()
        return templates.TemplateResponse(
            "services.html",
            template_context(request, session, services=services_list),
        )


@app.get("/services/{slug}", name="service_detail")
def service_detail(request: Request, slug: str):
    with SessionLocal() as session:
        service = session.scalar(select(Service).where(Service.slug == slug))
        return templates.TemplateResponse(
            "service_detail.html",
            template_context(request, session, service=service),
        )


@app.get("/journal", name="journal")
def journal(request: Request):
    with SessionLocal() as session:
        posts = session.scalars(
            select(Post).where(Post.status == "published").order_by(Post.published_at.desc(), Post.created_at.desc())
        ).all()
        return templates.TemplateResponse(
            "journal.html",
            template_context(request, session, posts=posts),
        )


@app.get("/journal/{slug}", name="post_detail")
def post_detail(request: Request, slug: str):
    with SessionLocal() as session:
        post = session.scalar(select(Post).where(Post.slug == slug))
        if post and post.status != "published" and not is_admin(request):
            return redirect_to("/journal")
        return templates.TemplateResponse(
            "post_detail.html",
            template_context(request, session, post=post),
        )


@app.get(f"{ADMIN_BASE_PATH}/login", name="admin_login")
def admin_login(request: Request):
    with SessionLocal() as session:
        if get_current_admin_user(session, request):
            return redirect_to(admin_path())
        return templates.TemplateResponse("admin/login.html", template_context(request, session))


@app.post(f"{ADMIN_BASE_PATH}/login", name="admin_login_submit")
async def admin_login_submit(request: Request):
    form = await request.form()
    username = str(form.get("username", ""))
    password = str(form.get("password", ""))
    with SessionLocal() as session:
        user = session.scalar(select(AdminUser).where(AdminUser.username == username))
        if user and user.is_active == "true" and check_password_hash(user.password_hash, password):
            request.session["admin_user_id"] = user.id
            flash(request, "success", "Welcome back. You are now signed in.")
            return redirect_to(admin_path())
        flash(request, "error", "Invalid username or password.")
        return redirect_to(admin_path("/login"))


@app.get(f"{ADMIN_BASE_PATH}/logout", name="admin_logout")
def admin_logout(request: Request):
    request.session.clear()
    flash(request, "success", "You have been signed out.")
    return redirect_to(admin_path("/login"))


@app.get(ADMIN_BASE_PATH, name="admin_dashboard")
def admin_dashboard(request: Request):
    with SessionLocal() as session:
        current_user = require_admin_user(request, session)
        if isinstance(current_user, RedirectResponse):
            return current_user
        pages = session.scalars(select(Page).order_by(Page.slug.asc())).all()
        services = session.scalars(select(Service).order_by(Service.sort_order.asc())).all()
        posts = session.scalars(select(Post).order_by(Post.updated_at.desc())).all()
        contact_fields = session.scalars(select(ContactField).order_by(ContactField.sort_order.asc())).all()
        nav_items = session.scalars(select(NavItem).order_by(NavItem.sort_order.asc())).all()
        users = session.scalars(select(AdminUser).order_by(AdminUser.username.asc())).all()
        content_snippets = session.scalars(
            select(ContentSnippet).where(ContentSnippet.group_name.in_(["homepage", "footer"])).order_by(ContentSnippet.group_name.asc(), ContentSnippet.sort_order.asc())
        ).all()
        return templates.TemplateResponse(
            "admin/dashboard.html",
            template_context(
                request,
                session,
                pages=pages,
                services=services,
                posts=posts,
                contact_fields=contact_fields,
                nav_items=nav_items,
                users=users,
                content_snippets=content_snippets,
            ),
        )


@app.get(f"{ADMIN_BASE_PATH}/settings", name="admin_settings")
def admin_settings(request: Request):
    with SessionLocal() as session:
        current_user = require_full_admin(request, session)
        if isinstance(current_user, RedirectResponse):
            return current_user
        return templates.TemplateResponse(
            "admin/settings_form.html",
            template_context(request, session, settings=get_settings(session)),
        )


@app.post(f"{ADMIN_BASE_PATH}/settings", name="admin_settings_save")
async def admin_settings_save(request: Request):
    form = await request.form()
    with SessionLocal() as session:
        current_user = require_full_admin(request, session)
        if isinstance(current_user, RedirectResponse):
            return current_user
        settings = get_settings(session)
        settings.company_name = str(form["company_name"])
        settings.tagline = str(form["tagline"])
        settings.hero_title = str(form["hero_title"])
        settings.hero_subtitle = str(form["hero_subtitle"])
        settings.intro_title = str(form["intro_title"])
        settings.intro_body = str(form["intro_body"])
        settings.contact_email = str(form["contact_email"])
        settings.contact_phone = str(form["contact_phone"])
        settings.location = str(form["location"])
        settings.coverage = str(form["coverage"])
        settings.investment_note = str(form["investment_note"])
        logo_file = form.get("logo")
        if logo_file and getattr(logo_file, "filename", ""):
            saved_name = secure_upload_name(logo_file.filename)
            if saved_name:
                content = await logo_file.read()
                (LOGOS_DIR / saved_name).write_bytes(content)
                settings.logo_path = f"/static/uploads/logos/{saved_name}"
        session.commit()
    flash(request, "success", "Site settings updated.")
    return redirect_to(admin_path())


@app.get(f"{ADMIN_BASE_PATH}/users/new", name="new_admin_user")
def new_admin_user(request: Request):
    with SessionLocal() as session:
        current_user = require_full_admin(request, session)
        if isinstance(current_user, RedirectResponse):
            return current_user
        return templates.TemplateResponse(
            "admin/user_form.html",
            template_context(request, session, managed_user=None),
        )


@app.post(f"{ADMIN_BASE_PATH}/users/new", name="new_admin_user_save")
async def new_admin_user_save(request: Request):
    form = await request.form()
    with SessionLocal() as session:
        current_user = require_full_admin(request, session)
        if isinstance(current_user, RedirectResponse):
            return current_user
        username = str(form.get("username", "")).strip()
        password = str(form.get("password", ""))
        if not username or not password:
            flash(request, "error", "Username and password are required.")
            return redirect_to(admin_path("/users/new"))
        if session.scalar(select(AdminUser).where(AdminUser.username == username)):
            flash(request, "error", "That username is already in use.")
            return redirect_to(admin_path("/users/new"))
        session.add(
            AdminUser(
                username=username,
                password_hash=generate_password_hash(password),
                role=str(form.get("role") or CONTENT_MODERATOR_ROLE),
                is_active="true" if form.get("is_active") else "false",
            )
        )
        session.commit()
    flash(request, "success", "Admin user created.")
    return redirect_to(admin_path())


@app.get(f"{ADMIN_BASE_PATH}/users/{{user_id}}/edit", name="edit_admin_user")
def edit_admin_user(request: Request, user_id: int):
    with SessionLocal() as session:
        current_user = require_full_admin(request, session)
        if isinstance(current_user, RedirectResponse):
            return current_user
        managed_user = session.get(AdminUser, user_id)
        if not managed_user:
            flash(request, "error", "User not found.")
            return redirect_to(admin_path())
        return templates.TemplateResponse(
            "admin/user_form.html",
            template_context(request, session, managed_user=managed_user),
        )


@app.post(f"{ADMIN_BASE_PATH}/users/{{user_id}}/edit", name="edit_admin_user_save")
async def edit_admin_user_save(request: Request, user_id: int):
    form = await request.form()
    with SessionLocal() as session:
        current_user = require_full_admin(request, session)
        if isinstance(current_user, RedirectResponse):
            return current_user
        managed_user = session.get(AdminUser, user_id)
        if not managed_user:
            flash(request, "error", "User not found.")
            return redirect_to(admin_path())
        requested_role = str(form.get("role") or managed_user.role)
        requested_active = "true" if form.get("is_active") else "false"
        new_username = str(form.get("username", "")).strip()
        if not new_username:
            flash(request, "error", "Username is required.")
            return redirect_to(admin_path(f"/users/{user_id}/edit"))
        duplicate = session.scalar(select(AdminUser).where(AdminUser.username == new_username, AdminUser.id != user_id))
        if duplicate:
            flash(request, "error", "That username is already in use.")
            return redirect_to(admin_path(f"/users/{user_id}/edit"))
        if managed_user.role == FULL_ADMIN_ROLE and full_admin_count(session) == 1:
            if requested_role != FULL_ADMIN_ROLE or requested_active != "true":
                flash(request, "error", "At least one active full admin account must remain.")
                return redirect_to(admin_path(f"/users/{user_id}/edit"))
        managed_user.username = new_username
        managed_user.role = requested_role
        managed_user.is_active = requested_active
        password = str(form.get("password", "")).strip()
        if password:
            managed_user.password_hash = generate_password_hash(password)
        session.commit()
    flash(request, "success", "Admin user updated.")
    return redirect_to(admin_path())


@app.post(f"{ADMIN_BASE_PATH}/users/{{user_id}}/delete", name="delete_admin_user")
def delete_admin_user(request: Request, user_id: int):
    with SessionLocal() as session:
        current_user = require_full_admin(request, session)
        if isinstance(current_user, RedirectResponse):
            return current_user
        managed_user = session.get(AdminUser, user_id)
        if not managed_user:
            flash(request, "error", "User not found.")
            return redirect_to(admin_path())
        if managed_user.id == current_user.id:
            flash(request, "error", "You cannot delete the account you are using right now.")
            return redirect_to(admin_path())
        if managed_user.role == FULL_ADMIN_ROLE and managed_user.is_active == "true" and full_admin_count(session) == 1:
            flash(request, "error", "At least one active full admin account must remain.")
            return redirect_to(admin_path())
        session.delete(managed_user)
        session.commit()
    flash(request, "success", "Admin user deleted.")
    return redirect_to(admin_path())


@app.get(f"{ADMIN_BASE_PATH}/pages/new", name="new_page")
def new_page(request: Request):
    with SessionLocal() as session:
        current_user = require_admin_user(request, session)
        if isinstance(current_user, RedirectResponse):
            return current_user
        return templates.TemplateResponse("admin/page_form.html", template_context(request, session, page=None))


@app.post(f"{ADMIN_BASE_PATH}/pages/new", name="new_page_save")
async def new_page_save(request: Request):
    form = await request.form()
    title = str(form["title"])
    slug = slugify(str(form.get("slug") or title))
    with SessionLocal() as session:
        current_user = require_admin_user(request, session)
        if isinstance(current_user, RedirectResponse):
            return current_user
        session.add(
            Page(
                slug=slug,
                title=title,
                subtitle=str(form["subtitle"]),
                body=str(form["body"]),
                cta_text=str(form["cta_text"]),
                cta_link=str(form["cta_link"]),
            )
        )
        session.commit()
    flash(request, "success", "Page created.")
    return redirect_to(admin_path())


@app.get(f"{ADMIN_BASE_PATH}/pages/{{slug}}/edit", name="edit_page")
def edit_page(request: Request, slug: str):
    with SessionLocal() as session:
        current_user = require_admin_user(request, session)
        if isinstance(current_user, RedirectResponse):
            return current_user
        page = session.scalar(select(Page).where(Page.slug == slug))
        return templates.TemplateResponse(
            "admin/page_form.html",
            template_context(request, session, page=page),
        )


@app.post(f"{ADMIN_BASE_PATH}/pages/{{slug}}/edit", name="edit_page_save")
async def edit_page_save(request: Request, slug: str):
    form = await request.form()
    with SessionLocal() as session:
        current_user = require_admin_user(request, session)
        if isinstance(current_user, RedirectResponse):
            return current_user
        page = session.scalar(select(Page).where(Page.slug == slug))
        page.title = str(form["title"])
        page.slug = slugify(str(form.get("slug") or page.title))
        page.subtitle = str(form["subtitle"])
        page.body = str(form["body"])
        page.cta_text = str(form["cta_text"])
        page.cta_link = str(form["cta_link"])
        session.commit()
    flash(request, "success", f"{page.slug.title()} page updated.")
    return redirect_to(admin_path())


@app.post(f"{ADMIN_BASE_PATH}/pages/{{slug}}/delete", name="delete_page")
def delete_page(request: Request, slug: str):
    with SessionLocal() as session:
        current_user = require_admin_user(request, session)
        if isinstance(current_user, RedirectResponse):
            return current_user
        page = session.scalar(select(Page).where(Page.slug == slug))
        if page:
            session.delete(page)
            session.commit()
    flash(request, "success", "Page deleted.")
    return redirect_to(admin_path())


@app.get(f"{ADMIN_BASE_PATH}/services/new", name="new_service")
def new_service(request: Request):
    with SessionLocal() as session:
        current_user = require_admin_user(request, session)
        if isinstance(current_user, RedirectResponse):
            return current_user
        return templates.TemplateResponse(
            "admin/service_form.html",
            template_context(request, session, service=None),
        )


@app.post(f"{ADMIN_BASE_PATH}/services/new", name="new_service_save")
async def new_service_save(request: Request):
    form = await request.form()
    title = str(form["title"])
    with SessionLocal() as session:
        current_user = require_admin_user(request, session)
        if isinstance(current_user, RedirectResponse):
            return current_user
        session.add(
            Service(
                title=title,
                slug=slugify(str(form.get("slug") or title)),
                summary=str(form["summary"]),
                details=str(form["details"]),
                highlight=str(form["highlight"]),
                sort_order=int(form.get("sort_order") or 0),
            )
        )
        session.commit()
    flash(request, "success", "Service created.")
    return redirect_to(admin_path())


@app.get(f"{ADMIN_BASE_PATH}/services/{{service_id}}/edit", name="edit_service")
def edit_service(request: Request, service_id: int):
    with SessionLocal() as session:
        current_user = require_admin_user(request, session)
        if isinstance(current_user, RedirectResponse):
            return current_user
        service = session.get(Service, service_id)
        return templates.TemplateResponse(
            "admin/service_form.html",
            template_context(request, session, service=service),
        )


@app.post(f"{ADMIN_BASE_PATH}/services/{{service_id}}/edit", name="edit_service_save")
async def edit_service_save(request: Request, service_id: int):
    form = await request.form()
    with SessionLocal() as session:
        current_user = require_admin_user(request, session)
        if isinstance(current_user, RedirectResponse):
            return current_user
        service = session.get(Service, service_id)
        title = str(form["title"])
        service.title = title
        service.slug = slugify(str(form.get("slug") or title))
        service.summary = str(form["summary"])
        service.details = str(form["details"])
        service.highlight = str(form["highlight"])
        service.sort_order = int(form.get("sort_order") or 0)
        session.commit()
    flash(request, "success", "Service updated.")
    return redirect_to(admin_path())


@app.post(f"{ADMIN_BASE_PATH}/services/{{service_id}}/delete", name="delete_service")
def delete_service(request: Request, service_id: int):
    with SessionLocal() as session:
        current_user = require_admin_user(request, session)
        if isinstance(current_user, RedirectResponse):
            return current_user
        service = session.get(Service, service_id)
        if service:
            session.delete(service)
            session.commit()
    flash(request, "success", "Service deleted.")
    return redirect_to(admin_path())


@app.get(f"{ADMIN_BASE_PATH}/posts/new", name="new_post")
def new_post(request: Request):
    with SessionLocal() as session:
        current_user = require_admin_user(request, session)
        if isinstance(current_user, RedirectResponse):
            return current_user
        return templates.TemplateResponse(
            "admin/post_form.html",
            template_context(request, session, post=None),
        )


@app.post(f"{ADMIN_BASE_PATH}/posts/new", name="new_post_save")
async def new_post_save(request: Request):
    form = await request.form()
    title = str(form["title"])
    status = str(form["status"])
    with SessionLocal() as session:
        current_user = require_admin_user(request, session)
        if isinstance(current_user, RedirectResponse):
            return current_user
        image_path = ""
        image_file = form.get("image")
        if image_file and getattr(image_file, "filename", ""):
            saved_name = secure_upload_name(image_file.filename)
            if saved_name:
                content = await image_file.read()
                (POSTS_DIR / saved_name).write_bytes(content)
                image_path = f"/static/uploads/posts/{saved_name}"
        session.add(
            Post(
                title=title,
                slug=slugify(str(form.get("slug") or title)),
                excerpt=str(form["excerpt"]),
                body=str(form["body"]),
                image_path=image_path,
                status=status,
                published_at=datetime.now(UTC) if status == "published" else None,
            )
        )
        session.commit()
    flash(request, "success", "Post created.")
    return redirect_to(admin_path())


@app.get(f"{ADMIN_BASE_PATH}/posts/{{post_id}}/edit", name="edit_post")
def edit_post(request: Request, post_id: int):
    with SessionLocal() as session:
        current_user = require_admin_user(request, session)
        if isinstance(current_user, RedirectResponse):
            return current_user
        post = session.get(Post, post_id)
        return templates.TemplateResponse(
            "admin/post_form.html",
            template_context(request, session, post=post),
        )


@app.post(f"{ADMIN_BASE_PATH}/posts/{{post_id}}/edit", name="edit_post_save")
async def edit_post_save(request: Request, post_id: int):
    form = await request.form()
    with SessionLocal() as session:
        current_user = require_admin_user(request, session)
        if isinstance(current_user, RedirectResponse):
            return current_user
        post = session.get(Post, post_id)
        title = str(form["title"])
        post.title = title
        post.slug = slugify(str(form.get("slug") or title))
        post.excerpt = str(form["excerpt"])
        post.body = str(form["body"])
        image_file = form.get("image")
        if image_file and getattr(image_file, "filename", ""):
            saved_name = secure_upload_name(image_file.filename)
            if saved_name:
                content = await image_file.read()
                (POSTS_DIR / saved_name).write_bytes(content)
                post.image_path = f"/static/uploads/posts/{saved_name}"
        post.status = str(form["status"])
        if post.status == "published" and not post.published_at:
            post.published_at = datetime.now(UTC)
        if post.status == "draft":
            post.published_at = None
        post.updated_at = datetime.now(UTC)
        session.commit()
    flash(request, "success", "Post updated.")
    return redirect_to(admin_path())


@app.get(f"{ADMIN_BASE_PATH}/contact-fields/new", name="new_contact_field")
def new_contact_field(request: Request):
    with SessionLocal() as session:
        current_user = require_admin_user(request, session)
        if isinstance(current_user, RedirectResponse):
            return current_user
        return templates.TemplateResponse("admin/contact_field_form.html", template_context(request, session, field=None))


@app.post(f"{ADMIN_BASE_PATH}/contact-fields/new", name="new_contact_field_save")
async def new_contact_field_save(request: Request):
    form = await request.form()
    with SessionLocal() as session:
        current_user = require_admin_user(request, session)
        if isinstance(current_user, RedirectResponse):
            return current_user
        session.add(
            ContactField(
                label=str(form["label"]),
                name=slugify(str(form["name"])).replace("-", "_"),
                field_type=str(form["field_type"]),
                placeholder=str(form.get("placeholder") or ""),
                options=str(form.get("options") or ""),
                required="true" if form.get("required") else "false",
                sort_order=int(form.get("sort_order") or 0),
                is_active="true" if form.get("is_active") else "false",
            )
        )
        session.commit()
    flash(request, "success", "Contact field created.")
    return redirect_to(admin_path())


@app.get(f"{ADMIN_BASE_PATH}/contact-fields/{{field_id}}/edit", name="edit_contact_field")
def edit_contact_field(request: Request, field_id: int):
    with SessionLocal() as session:
        current_user = require_admin_user(request, session)
        if isinstance(current_user, RedirectResponse):
            return current_user
        field = session.get(ContactField, field_id)
        return templates.TemplateResponse("admin/contact_field_form.html", template_context(request, session, field=field))


@app.post(f"{ADMIN_BASE_PATH}/contact-fields/{{field_id}}/edit", name="edit_contact_field_save")
async def edit_contact_field_save(request: Request, field_id: int):
    form = await request.form()
    with SessionLocal() as session:
        current_user = require_admin_user(request, session)
        if isinstance(current_user, RedirectResponse):
            return current_user
        field = session.get(ContactField, field_id)
        field.label = str(form["label"])
        field.name = slugify(str(form["name"])).replace("-", "_")
        field.field_type = str(form["field_type"])
        field.placeholder = str(form.get("placeholder") or "")
        field.options = str(form.get("options") or "")
        field.required = "true" if form.get("required") else "false"
        field.sort_order = int(form.get("sort_order") or 0)
        field.is_active = "true" if form.get("is_active") else "false"
        session.commit()
    flash(request, "success", "Contact field updated.")
    return redirect_to(admin_path())


@app.post(f"{ADMIN_BASE_PATH}/contact-fields/{{field_id}}/delete", name="delete_contact_field")
def delete_contact_field(request: Request, field_id: int):
    with SessionLocal() as session:
        current_user = require_admin_user(request, session)
        if isinstance(current_user, RedirectResponse):
            return current_user
        field = session.get(ContactField, field_id)
        if field:
            session.delete(field)
            session.commit()
    flash(request, "success", "Contact field deleted.")
    return redirect_to(admin_path())


@app.get(f"{ADMIN_BASE_PATH}/nav-items/new", name="new_nav_item")
def new_nav_item(request: Request):
    with SessionLocal() as session:
        current_user = require_full_admin(request, session)
        if isinstance(current_user, RedirectResponse):
            return current_user
        return templates.TemplateResponse("admin/nav_item_form.html", template_context(request, session, item=None))


@app.post(f"{ADMIN_BASE_PATH}/nav-items/new", name="new_nav_item_save")
async def new_nav_item_save(request: Request):
    form = await request.form()
    with SessionLocal() as session:
        current_user = require_full_admin(request, session)
        if isinstance(current_user, RedirectResponse):
            return current_user
        session.add(
            NavItem(
                label=str(form["label"]),
                path=str(form["path"]),
                sort_order=int(form.get("sort_order") or 0),
                is_button="true" if form.get("is_button") else "false",
                is_active="true" if form.get("is_active") else "false",
            )
        )
        session.commit()
    flash(request, "success", "Navigation item created.")
    return redirect_to(admin_path())


@app.get(f"{ADMIN_BASE_PATH}/nav-items/{{item_id}}/edit", name="edit_nav_item")
def edit_nav_item(request: Request, item_id: int):
    with SessionLocal() as session:
        current_user = require_full_admin(request, session)
        if isinstance(current_user, RedirectResponse):
            return current_user
        item = session.get(NavItem, item_id)
        return templates.TemplateResponse("admin/nav_item_form.html", template_context(request, session, item=item))


@app.post(f"{ADMIN_BASE_PATH}/nav-items/{{item_id}}/edit", name="edit_nav_item_save")
async def edit_nav_item_save(request: Request, item_id: int):
    form = await request.form()
    with SessionLocal() as session:
        current_user = require_full_admin(request, session)
        if isinstance(current_user, RedirectResponse):
            return current_user
        item = session.get(NavItem, item_id)
        item.label = str(form["label"])
        item.path = str(form["path"])
        item.sort_order = int(form.get("sort_order") or 0)
        item.is_button = "true" if form.get("is_button") else "false"
        item.is_active = "true" if form.get("is_active") else "false"
        session.commit()
    flash(request, "success", "Navigation item updated.")
    return redirect_to(admin_path())


@app.post(f"{ADMIN_BASE_PATH}/nav-items/{{item_id}}/delete", name="delete_nav_item")
def delete_nav_item(request: Request, item_id: int):
    with SessionLocal() as session:
        current_user = require_full_admin(request, session)
        if isinstance(current_user, RedirectResponse):
            return current_user
        item = session.get(NavItem, item_id)
        if item:
            session.delete(item)
            session.commit()
    flash(request, "success", "Navigation item deleted.")
    return redirect_to(admin_path())


@app.get(f"{ADMIN_BASE_PATH}/homepage-content", name="admin_homepage_content")
def admin_homepage_content(request: Request):
    with SessionLocal() as session:
        current_user = require_admin_user(request, session)
        if isinstance(current_user, RedirectResponse):
            return current_user
        snippets = session.scalars(
            select(ContentSnippet).where(ContentSnippet.group_name.in_(["homepage", "footer"])).order_by(ContentSnippet.group_name.asc(), ContentSnippet.sort_order.asc())
        ).all()
        return templates.TemplateResponse("admin/homepage_content_form.html", template_context(request, session, snippets=snippets))


@app.post(f"{ADMIN_BASE_PATH}/homepage-content", name="admin_homepage_content_save")
async def admin_homepage_content_save(request: Request):
    form = await request.form()
    with SessionLocal() as session:
        current_user = require_admin_user(request, session)
        if isinstance(current_user, RedirectResponse):
            return current_user
        snippets = session.scalars(
            select(ContentSnippet).where(ContentSnippet.group_name.in_(["homepage", "footer"])).order_by(ContentSnippet.group_name.asc(), ContentSnippet.sort_order.asc())
        ).all()
        for snippet in snippets:
            if snippet.key in form:
                snippet.value = str(form[snippet.key])
        session.commit()
    flash(request, "success", "Homepage content updated.")
    return redirect_to(admin_path())


@app.post(f"{ADMIN_BASE_PATH}/posts/{{post_id}}/delete", name="delete_post")
def delete_post(request: Request, post_id: int):
    with SessionLocal() as session:
        current_user = require_admin_user(request, session)
        if isinstance(current_user, RedirectResponse):
            return current_user
        post = session.get(Post, post_id)
        if post:
            session.delete(post)
            session.commit()
    flash(request, "success", "Post deleted.")
    return redirect_to(admin_path())
