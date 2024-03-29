import logging
from collections import UserList

LOGGER = logging.getLogger("csv-eval")

FIELD_VAR_NAME = "field"


class ExpandableList(UserList):
    class AccessProxy:
        def __init__(self, proxied_obj, access_cast):
            self.proxied_obj = proxied_obj
            self.accesss_cast = access_cast

        def __getitem__(self, item):
            return self.accesss_cast(self.proxied_obj.__getitem__(item))

        def __setitem__(self, i, item):
            return self.proxied_obj.__setitem__(i, item)

    ################################################################

    def __init__(self, initlist=None):
        if initlist is None:
            initlist = []
        super().__init__(initlist)
        self._stored_header = None
        self._extra_headers = []
        self.as_float = self.__class__.AccessProxy(
            proxied_obj=self,
            access_cast=float,
        )

        self.as_int = self.__class__.AccessProxy(
            proxied_obj=self,
            access_cast=int,
        )

        self.as_str = self.__class__.AccessProxy(
            proxied_obj=self,
            access_cast=str,
        )
        import sys, csv

        self.csv_writer = csv.writer(sys.stdout)

    def _set_header_content(self, content, extra_headers):
        self.data = content
        self._extra_headers = extra_headers
        self._stored_header = {
            key: i for i, key in enumerate(self.data + self._extra_headers)
        }
        self.extend(self._extra_headers)

    def __search_for_extra_header_when_headers_are_off(self, index: str):
        # look at the extra header and see if we can find a match
        try:
            extra_header_idx = self._extra_headers.index(index)
        except ValueError:
            raise RuntimeError(
                f"Header is disabled, but the given indexer is of "
                f"string type: {index}"
            )
        else:
            return len(self) - len(self._extra_headers) + extra_header_idx

    def __setitem__(self, idx, item):
        if isinstance(idx, int):
            if idx == len(self):  # jit append
                self.append("")
        elif isinstance(idx, str):
            # first convert it back to our list index
            if self._stored_header is not None:
                idx = self._stored_header[idx]
            else:
                # look at the extra header and see if we can find a match
                idx = self.__search_for_extra_header_when_headers_are_off(idx)

            while idx >= len(self):
                self.append("")
        return super().__setitem__(idx, str(item))

    def __getitem__(self, idx):
        if isinstance(idx, str):
            if self._stored_header is None:
                # look at the extra header and see if we can find a match
                idx = self.__search_for_extra_header_when_headers_are_off(idx)
            else:
                # directly retrieve it from our dict
                idx = self._stored_header[idx]
        return super().__getitem__(idx)

    def print_field(self, *indices):
        if len(indices) > 0:
            data = (self[i] for i in indices)
        else:
            data = self.data
        self.csv_writer.writerow(data)

    def __repr__(self):
        # skip using custom getitem
        return ",".join(self.data)
