"""Client module for async requests to the vShield API."""

from __future__ import annotations, print_function

from typing import TYPE_CHECKING

from httpx import AsyncClient, Request

from .api_defs import (
    OperatingSystems,
    ServerActions,
    ServiceActions,
    _BillingRequests,
    _FirewallRequests,
    _ServerRequests,
    _ServiceRequests,
    _SystemRequests,
)
from .auth import _VShieldAuth
from .handlers import billing, firewall, servers, services, system

if TYPE_CHECKING:
    from typing import Literal, Optional

    from .api_defs import AutoRenew, Plans


class Client:
    """Client for sending requests to the vShield API.

    The naming convention for methods is similiar to a discord.py Client.
    Function names starting with fetch, send async requests and function names starting
    with get perform cache lookups.
    """

    __slots__ = ("_auth_key", "_session", "_balance", "_servers")

    # All Request constructing is done in public methods then passed to Client._request.
    def __init__(self, auth_key: str, **kwargs):
        self.auth_key = auth_key
        session = AsyncClient(auth=_VShieldAuth(auth_key), http2=True, **kwargs)
        self._session = session

    @property
    def auth_key(self) -> str:
        """Currently set authentication key."""
        return self._auth_key

    @auth_key.setter
    def auth_key(self, auth_key):
        try:
            int(auth_key, base=16)
        except ValueError:
            raise InvalidAuthKey(auth_key)
        self._auth_key = auth_key

    async def _request(self, req: Request):
        response = (await self._session.send(req)).json()
        if response["requestStatus"] == 0:
            raise BadRequestStatus(response["result"]["error"])

        return response["result"]

    async def fetch_plans(self):
        """Fetch available plans with their stock status.

        Returns:
            StockStatus:
                Current stock status of all plans.
        """
        method, url = _SystemRequests.GET_PLANS
        req = Request(method, url)
        response = await self._request(req)
        return system._get_list(response)

    async def fetch_pending_orders(self):
        """Fetch currently pending orders.

        Returns:
            list[PendingServer]:
                List of servers that are currently pending deployment.
        """
        method, url = _SystemRequests.GET_PENDING_ORDERS
        req = Request(method, url)
        response = await self._request(req)
        return system._get_pending_orders(response)

    async def fetch_task_info(self, task_id: int):
        """Fetch task information.

        Returns:
            Task:
                Task with the ID that was provided.
        """
        method, url = _SystemRequests.GET_TASK_INFO
        url = url.join(str(task_id))
        req = Request(method, url)
        response = await self._request(req)
        return system._get_task_info(response)

    async def fetch_services(self):
        """Fetchs all currently active services.

        Returns:
            tuple[DedicatedServer | Hosting, ...]:
                All currently active services.
        """
        method, url = _ServiceRequests.GET_LIST
        req = Request(method, url)
        response = await self._request(req)
        return services._get_list(response)

    async def fetch_service(self, service_id: int):
        """Fetch a single service."""
        method, url = _ServiceRequests.GET_INFO
        url = url.join(str(service_id))
        req = Request(method, url)
        response = await self._request(req)
        return services._get_service(response)

    async def create_service_task(
        self,
        service_id: int,
        task: ServiceActions,
        os: Optional[OperatingSystems] = None,
    ) -> bool:
        """Create a task on a dedicated server.

        Should not be used on hosting plans.

        Args:
            service_id (int): Service ID of the service to perform the task on.
            task (ServiceActions): Task to be performed on the service.
            os (Optional[OperatingSystems], optional):
                Should only be provided if the task is a reinstall. Defaults to None.

        Raises:
            ReinstallWithoutOS:
                Attempted reinstall without providing an operating system.

        Returns:
            bool: If the task was created successfuly returns True.
        """
        if task == ServiceActions.Reinstall and not os:
            raise ReinstallWithoutOS()
        method, url = _ServiceRequests.CREATE_TASK
        url = url.join(str(service_id))

        data = {
            "action": task.value,
        }
        if isinstance(os, OperatingSystems):
            data["os"] = os.value

        req = Request(method, url, data=data)
        response = await self._request(req)
        return services._create_task(response)

    async def set_service_auto_renew(
        self, service_id: int, auto_renew: AutoRenew
    ) -> AutoRenew:
        """Set the new auto-renew status for a service.

        Args:
            service_id (int): Service ID of the service to perform the task on.
            auto_renew (AutoRenew): An auto-renew status.

        Returns:
            AutoRenew:
                The new auto-renew status.
        """
        method, url = _ServiceRequests.SET_AUTO_RENEW
        url = url.join(str(service_id))
        data = {"status": auto_renew.value}
        req = Request(method, url, data=data)
        response = await self._request(req)
        return services._set_auto_renew(response)

    async def renew_service(self, service_id: int, months: Literal[1, 3, 6]):
        """Renew a specific service.

        Args:
            service_id (int): Service ID of the service to perform the task on.
            months (Literal[1, 3, 6]): Number of months to renew the server.

        Raises:
            InvalidParameter: Invalid value was provided for one of the parameters.

        Returns:
            Payment: The payment information returned by the API.
        """
        accepted_months = (1, 3, 6)
        if months not in accepted_months:
            raise InvalidParameter(months, accepted_months)
        method, url = _ServiceRequests.RENEW_SERVICE

        data = {"time": months}
        url = url.join(str(service_id))
        req = Request(method, url, data=data)
        response = await self._request(req)
        return services._renew(response)

    async def fetch_servers(self):
        """Fetch all servers.

        Servers returned will not have password information.

        Returns:
            tuple[Server, ...]:
                All of the servers found. Servers returned will not contain a password.
        """
        method, url = _ServerRequests.GET_LIST
        req = Request(method, url)
        response = await self._request(req)
        return servers._get_list(response)

    async def fetch_server(self, server_id: int):
        """Fetch a single server.

        Returned Server will have password information.

        Args:
            server_id (int): Server ID of the Server to lookup information.

        Returns:
            Server:
                Server object containing full information on a server.
                Including password information.
        """
        method, url = _ServerRequests.GET_INFO
        url = url.join(str(server_id))
        req = Request(method, url)
        response = await self._request(req)
        return servers._get_server(response)

    async def fetch_server_stats(self, server_id: int):
        """Fetch server stats.

        Args:
            server_id (int): Server ID of the server to get the statistics for.

        Returns:
            ServerStats: Contains stats for the server.
        """
        method, url = _ServerRequests.GET_GRAPHS
        url = url.join(str(server_id))
        req = Request(method, url)
        response = await self._request(req)
        return servers._get_server_stats(response)

    async def fetch_server_console(self, server_id: int):
        """Fetch url for console connection.

        Args:
            server_id (int): _description_

        Returns:
            str: URL for the console session.
        """
        method, url = _ServerRequests.GET_CONSOLE
        url = url.join(str(server_id))
        req = Request(method, url)
        response = await self._request(req)
        return servers._get_server_console(response)

    async def create_server_task(
        self, server_id: int, task: ServerActions, os: Optional[OperatingSystems]
    ) -> int:
        """Starts a task execution for corresponding server for the ID.

        Args:
            server_id (int): Server ID for the server to start the ask on.
            task (ServerActions): Task to be run on the server.
            os (Optional[OperatingSystems]):
                Choice of operating system.
                Required if the task to be performed is a reinstall.

        Raises:
            ReinstallWithoutOS:
                A reinstall task was started without providing an operating system.

        Returns:
            int: The task ID for the task that was created.
        """
        method, url = _ServerRequests.CREATE_TASK
        url = url.join(str(server_id))
        if task == ServerActions.Reinstall and not os:
            raise ReinstallWithoutOS()
        data = {"action": task.value}
        if isinstance(os, OperatingSystems):
            data["os"] = os.value

        req = Request(method, url, data=data)
        response = await self._request(req)
        return servers._create_server_task(response)

    async def set_server_auto_renew(self, server_id: int, auto_renew: AutoRenew):
        """Set the server's auto-renew status.

        Args:
            server_id (int): Server ID of the server to set the auto-renew status to.
            auto_renew (AutoRenew): The new auto-renew status.

        Returns:
            AutoRenew: The new auto-renew status.
        """
        method, url = _ServerRequests.SET_AUTO_RENEW
        url = url.join(str(server_id))
        data = {"status": auto_renew.value}
        req = Request(method, url, data=data)
        response = await self._request(req)
        return servers._set_auto_renew(response)

    async def set_server_hostname(self, server_id: int, hostname: str):
        """Set the server's new hostname."""
        if not hostname.isalpha():
            raise InvalidParameter("Hostname can only contain alphabetic characters.")
        method, url = _ServerRequests.SET_HOSTNAME
        url = url.join(str(server_id))
        data = {"hostname": hostname}
        req = Request(method, url, data=data)
        response = await self._request(req)
        return servers._set_hostname(response)

    async def upgrade_server(self, server_id: int, upgrade: Plans):
        """Upgrade the server to a higher tier.

        Provided upgrade plan must be in the same class and a higher tier than what
        the servers current plan is.
        """
        method, url = _ServerRequests.UPGRADE_SERVER
        url = url.join(str(server_id))
        data = {"plan": str(upgrade.value)}
        req = Request(method, url, data=data)
        response = await self._request(req)
        return servers._upgrade(response)

    async def change_server_ip(self, server_id):
        """Change the server's IP."""
        method, url = _ServerRequests.CHANGE_IP
        url = url.join(str(server_id))
        req = Request(method, url)
        response = await self._request(req)
        return servers._change_ip(response)

    async def renew_server(self, server_id: int, days: int):
        """Renew the server.

        Args:
            server_id:
                Server ID for the corresponding server.
            days:
                Value must not be less than 1 and more than 365.
        """
        if not 1 <= days <= 365:
            raise ValueError(
                f"Expected day value to be inclusively between 1 and 365. "
                f"{days} was found."
            )

        method, url = _ServerRequests.RENEW_SERVER
        url = url.join(str(server_id))
        req = Request(method, url)
        response = await self._request(req)
        return servers._renew(response)

    async def delete_server(self, server_id: int):
        """Deletes the server with the specified server_id.

        There is no way to reverse this. This should be called with caution.

        Args:
            server_id:
                Server ID for the corresponding server.
        """
        method, url = _ServerRequests.DELETE_SERVER
        url = url.join(str(server_id))
        req = Request(method, url)
        response = await self._request(req)
        return servers._delete(response)

    async def order_server(
        self, plan: Plans, location: str, hostname: str, os: OperatingSystems, days: int
    ):
        """Place an order for a new server.

        The server can be retrieved via
        :func:`~Client.fetch_servers`, :func:`~Client.fetch_server` or
        :func:`~Client.fetch_pending_orders` if the order is pending.

        Args:
            plan:
                The plan to be ordered.
            location:
                The location of the order.
                Valid locations of a plan can be retreived via :class:`~StockStatus`.
            hostname:
                The hostname of the new server.
                Symbols are not allowed in the provided string.
            os:
                Operating system to be installed on the server.
                If a reinstall is to be performed,
                an operating system from :class:`~OperatingSystems` must be provided.
            days:
                Value must not be less than 1 or more than 365.

        Raises:
            ValueError:
                The days value was less than 1 or more than 365.
            InvalidParameter:
                The hostname value contains alpabetic characters.
        """
        if not 1 <= days <= 365:
            raise ValueError(
                f"Expected day value to be inclusively between 1 "
                f"and 365. {days} was found."
            )

        if not hostname.isalpha():
            raise InvalidParameter("Hostname can only contain alphabetic characters.")

        data = {
            "location": location,
            "hostname": hostname,
            "os": os.value,
            "time": days,
        }
        method, url = _ServerRequests.ORDER_SERVER
        req = Request(method, url, data=data)
        response = await self._request(req)
        return servers._order(response)

    async def fetch_balance(self):
        """Fetch the accounts current balance."""
        method, url = _BillingRequests.GET_BALANCE
        req = Request(method, url)
        response = await self._request(req)
        return billing._get_balance(response)

    async def fetch_transactions(self):
        """Fetch list of transactions."""
        method, url = _BillingRequests.GET_TRANSACTIONS
        req = Request(method, url)
        response = await self._request(req)
        return billing._get_transactions(response)

    async def fetch_invoices(self):
        """Fetch list of invoices."""
        method, url = _BillingRequests.GET_INVOICES
        req = Request(method, url)
        response = await self._request(req)
        return billing._get_invoices(response)

    async def fetch_invoice(self, invoice_id: int):
        """Fetch a specific invoice.

        Args:
            invoice_id (int): Invoice ID to fetch information from.

        Returns:
            Invoice: Invoice object containing invoice information.
        """
        method, url = _BillingRequests.GET_INVOICE_INFO
        url = url.join(str(invoice_id))
        req = Request(method, url)
        response = await self._request(req)
        return billing._get_invoice(response)


class InvalidAuthKey(Exception):
    """Raised upon finding an invalid format (non base16) auth key."""

    def __init__(self, auth_key):
        super().__init__(
            f"Invalid auth key was provided, auth key must be a base16 string. "
            f"{auth_key} is not a valid key."
        )


class BadRequestStatus(Exception):
    """Raised if there is an unkown API error returned.

    Can also mean format wise correct but invalid auth key was provided.
    """

    def __init__(self, api_error: str):
        super().__init__(
            f'requestStatus was returned "0". Error returned from API: "{api_error}"'
        )


class ReinstallWithoutOS(Exception):
    """Raised if a reinstall is requested without specifying an Operating system."""

    def __init__(self):
        super().__init__(
            "Attempted reinstall task without providing an Operating System."
        )


class InvalidParameter(Exception):
    """Raised if an invalid parameter was provided for any function or request."""

    def __init__(self, provided_val, accepted_vals=None):
        super().__init__(f"Expected one of {accepted_vals}, found {provided_val}")