"""Use case: read one page of a filtered, projected table."""

from application.dtos import FilterCriterionQuery, ListRecordsQuery
from application.interfaces import Repository
from application.validators import ListRecordsQueryValidator
from domain.errors import DomainError
from domain.value_objects import Filter, FilterCriterion, Pagination, ResultSet
from returns.result import Failure, Result


def _to_domain_filter(criteria: tuple[FilterCriterionQuery, ...]) -> Filter:
    """Translate validated wire criteria into domain value objects.

    Total by construction: the validator already rejected every shape the
    domain would refuse, so this mapping cannot raise.
    """
    return Filter(
        tuple(
            FilterCriterion(
                column=item.column, operator=item.operator, value=item.value
            )
            for item in criteria
        )
    )


class GetListRecords:
    """Validate the request, then ask the repository port for one page.

    The use case knows the port, never the SQL adapter: dependency inversion
    lets the same logic run against a mock, SQLite, or SQL Server without a
    single change here.
    """

    def __init__(
        self,
        repository: Repository,
        validator: ListRecordsQueryValidator | None = None,
    ) -> None:
        self._repository = repository
        self._validator = validator or ListRecordsQueryValidator()

    async def execute(
        self, query: ListRecordsQuery
    ) -> Result[ResultSet, DomainError]:
        """Return ``Success(ResultSet)`` or ``Failure(DomainError)``.

        Expected failures (invalid input, unknown table or column) travel as
        values; unexpected ones keep raising.
        """
        validation = self._validator.validate(query)
        if isinstance(validation, Failure):
            return Failure(validation.failure())

        pagination = Pagination(page=query.page, page_size=query.page_size)
        return await self._repository.get_result_set(
            pagination=pagination,
            table=query.table,
            columns=query.columns,
            schema=query.schema,
            filters=_to_domain_filter(query.filters),
        )
