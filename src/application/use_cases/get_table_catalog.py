"""Use case: read one page of the database table catalog."""

from application.dtos import TableCatalogQuery
from application.interfaces import Repository
from application.validators import TableCatalogQueryValidator
from domain.errors import DomainError
from domain.value_objects import Pagination, ResultSet
from returns.result import Failure, Result


class GetTableCatalog:
    """Validate the request, then ask the repository port for one page.

    The use case knows the port, never the SQL adapter: dependency inversion
    lets the same logic run against a mock, SQLite, or SQL Server without a
    single change here.
    """

    def __init__(
        self,
        repository: Repository,
        validator: TableCatalogQueryValidator | None = None,
    ) -> None:
        self._repository = repository
        self._validator = validator or TableCatalogQueryValidator()

    async def execute(
        self, query: TableCatalogQuery
    ) -> Result[ResultSet, DomainError]:
        """Return ``Success(ResultSet)`` or ``Failure(DomainError)``.

        Expected failures (invalid input, unknown schema) travel as values;
        unexpected ones keep raising.
        """
        validation = self._validator.validate(query)
        if isinstance(validation, Failure):
            return Failure(validation.failure())

        pagination = Pagination(page=query.page, page_size=query.page_size)
        return await self._repository.get_table_catalog(pagination, query.schema)
