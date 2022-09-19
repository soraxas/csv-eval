from collections import UserList

FIELD_VAR_NAME = "field"


class ExpandableList(UserList):
    __stored_header = None
    __extra_headers = []

    @classmethod
    def add_extra_headers(cls, extra_headers):
        cls.__extra_headers = extra_headers

    def __init__(self, initlist, is_header=False, access_cast=lambda x: x):
        super().__init__(initlist)
        self.access_cast = access_cast
        if is_header:
            self.__class__.__stored_header = {
                key: i
                for i, key in enumerate(self.data + self.__class__.__extra_headers)
            }
            self.extend(self.__extra_headers)

    @property
    def as_float(self):
        proxy = self.__class__(self, access_cast=float)
        return proxy

    @property
    def as_int(self):
        proxy = self.__class__(self, access_cast=int)
        return proxy

    @property
    def as_str(self):
        proxy = self.__class__(self, access_cast=str)
        return proxy

    def __search_for_extra_header_when_headers_are_off(self, index: str):
        # look at the extra header and see if we can find a match
        try:
            extra_header_idx = self.__extra_headers.index(index)
        except ValueError:
            raise RuntimeError(
                f"Header is disabled, but the given indexer is of "
                f"string type: {index}"
            )
        else:
            return len(self) - len(self.__extra_headers) + extra_header_idx

    def __setitem__(self, i, item):
        if isinstance(i, int):
            if i == len(self):
                self.append("")
        elif isinstance(i, str):
            if self.__stored_header is None:
                # look at the extra header and see if we can find a match
                i = self.__search_for_extra_header_when_headers_are_off(i)

            else:
                i = self.__stored_header[i]
            while i >= len(self):
                self.append("")
        return super().__setitem__(i, item)

    def __getitem__(self, item):
        if isinstance(item, str):
            if self.__stored_header is None:
                # look at the extra header and see if we can find a match
                item = self.__search_for_extra_header_when_headers_are_off(item)
            else:
                item = self.__stored_header[item]
        return self.access_cast(super().__getitem__(item))

    def __repr__(self):
        return ",".join(map(str, self))
