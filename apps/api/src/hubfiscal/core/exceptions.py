class HubFiscalError(Exception):
    code = "hubfiscal_error"
    status_code = 400


class NotFoundError(HubFiscalError):
    code = "not_found"
    status_code = 404


class ForbiddenError(HubFiscalError):
    code = "forbidden"
    status_code = 403


class ConflictError(HubFiscalError):
    code = "conflict"
    status_code = 409
