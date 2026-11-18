from django.utils.cache import add_never_cache_headers


class PrivateAPIResponseMixin:
    """Match the website's never-cache policy for account-specific responses."""

    def finalize_response(self, request, response, *args, **kwargs):
        response = super().finalize_response(request, response, *args, **kwargs)
        add_never_cache_headers(response)
        return response
