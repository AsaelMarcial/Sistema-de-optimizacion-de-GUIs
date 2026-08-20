from dataclasses import dataclass, field


@dataclass(slots=True)
class RequestInformation:
    timing: float
    url: str
    resource_type: str
    method: str
    status: str
    status_code: int | None = None
    message: str | None = None

    @property
    def is_local(self) -> bool:
        return self.url.startswith("http://127.0.0.1")

@dataclass(slots=True)
class RequestRecords:
    records: list[RequestInformation] = field(default_factory=list)

    def add_request(
        self,
        timing: float,
        url: str,
        resource_type: str,
        method: str,
        status: str,
        status_code: int | None = None,
        message: str | None = None,
    ) -> RequestInformation:
        request = RequestInformation(
            timing=timing,
            url=url,
            resource_type=resource_type,
            method=method,
            status=status,
            status_code=status_code,
            message=message,
        )

        self.records.append(request)

        return request

    def clear(self) -> None:
        self.records.clear()

    def all_records(self) -> list[RequestInformation]:
        return sorted(
            self.records,
            key=lambda request: request.timing,
        )

    def request(
        self,
        timing: float,
    ) -> RequestInformation | None:
        return next(
            filter(
                lambda request: request.timing == timing,
                self.records,
            ),
            None,
        )
