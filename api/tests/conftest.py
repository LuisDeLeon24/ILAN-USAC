import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete

from app.core.security import hash_password
from app.db.session import SessionLocal
from app.main import app
from app.models.entities import (
    AgentConversation,
    AgentMessage,
    AgentToolCall,
    AlertContact,
    AlertLog,
    Camera,
    Device,
    Event,
    ExclusionArea,
    Organization,
    PricingPlan,
    Sensor,
    Site,
    UsageRecord,
    UsageReport,
    User,
    Zone,
)


def purge_organization(organization_id: uuid.UUID) -> None:
    db = SessionLocal()
    try:
        for model in (
            AgentToolCall,
            AgentMessage,
            AgentConversation,
            AlertLog,
            AlertContact,
            UsageReport,
            UsageRecord,
            PricingPlan,
            Event,
            Sensor,
            Zone,
            ExclusionArea,
            Camera,
            Device,
            Site,
            User,
        ):
            db.execute(delete(model).where(model.organization_id == organization_id))
        db.execute(delete(Organization).where(Organization.id == organization_id))
        db.commit()
    finally:
        db.close()


def create_account(role: str = "admin") -> dict[str, str]:
    db = SessionLocal()
    try:
        organization = Organization(name=f"Org {uuid.uuid4()}", timezone="America/Guatemala")
        db.add(organization)
        db.flush()
        email = f"user-{uuid.uuid4()}@example.com"
        db.add(
            User(
                organization_id=organization.id,
                email=email,
                full_name="Cuenta de prueba",
                role=role,
                password_hash=hash_password("password1"),
            )
        )
        db.commit()
        return {
            "email": email,
            "password": "password1",
            "organization_id": str(organization.id),
            "role": role,
        }
    finally:
        db.close()


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def accounts():
    created: list[uuid.UUID] = []

    def make(role: str = "admin") -> dict[str, str]:
        account = create_account(role)
        created.append(uuid.UUID(account["organization_id"]))
        return account

    yield make
    for organization_id in created:
        purge_organization(organization_id)


def auth_header(client: TestClient, account: dict[str, str]) -> dict[str, str]:
    response = client.post("/auth/login", json={"email": account["email"], "password": account["password"]})
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}
