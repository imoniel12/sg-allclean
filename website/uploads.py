from django.core.files.uploadhandler import FileUploadHandler, StopUpload


class QuoteUploadLimit(FileUploadHandler):
    """Cap streamed uploads before Django writes temporary files."""
    def __init__(self, request=None):
        super().__init__(request)
        self.total = 0

    def receive_data_chunk(self, raw_data, start):
        self.total += len(raw_data)
        if self.total > 16 * 1024 * 1024:
            self.request.upload_limit_exceeded = True
            raise StopUpload(connection_reset=False)
        return raw_data

    def file_complete(self, file_size):
        return None
