import pytest
from test_api import client

from vshieldpy.api_defs.auto_renew import AutoRenew
from vshieldpy.api_defs.operating_systems import OperatingSystems
from vshieldpy.api_defs.tasks import ServiceActions
from vshieldpy.exceptions.parameter_exceptions import ReinstallWithoutOS
from vshieldpy.products.service import Hosting

pytestmark = pytest.mark.anyio


async def test_get_service_list():
    services = await client.fetch_services()
    assert len(services.services) == 2
    assert len(services.hostings) == 1
    assert len(services.dedicated_servers) == 1


async def test_get_service_info():
    service_info = await client.fetch_service(0)
    assert service_info is not None
    assert type(service_info) == Hosting


async def test_create_task_service():
    task = await client.create_service_task(
        1, ServiceActions.Reinstall, OperatingSystems.Ubuntu20
    )
    assert task

    with pytest.raises(ReinstallWithoutOS):
        await client.create_service_task(1, ServiceActions.Reinstall, None)


async def test_service_manage_auto_renew():
    new_renew_state = await client.set_service_auto_renew(1, AutoRenew.Enable)
    assert AutoRenew.Enable == new_renew_state


async def test_service_renew():
    payment = await client.renew_service(1, 3)
    assert payment.invoice_id is None
