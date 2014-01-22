#!/usr/bin/env python
# This code is based on slumber, but dont uses requests.
# Now we are using pure urllib2.
import urllib2
import base64
import urllib
import urlparse
import posixpath
import pprint
import MultipartPostHandler
from django.http import HttpResponse
from exceptions import *
from serialize import Serializer

class RequestWithMethod(urllib2.Request):
    def __init__(self, method, *args, **kwargs):
        self._method = method
        urllib2.Request.__init__(self, *args, **kwargs)

    def get_method(self):
        return self._method

class ResourceCommon(object):

    def _url_join(self, base, *args):
        """
        Helper function to join an arbitrary number of url segments together.
        """
        scheme, netloc, path, query, fragment = urlparse.urlsplit(base)
        path = path if len(path) else "/"
        path = posixpath.join(path, *[('%s' % x) for x in args])
        return urlparse.urlunsplit([scheme, netloc, path, query, fragment])

    def __getattr__(self, item):
        if item.startswith("_"):
            raise AttributeError(item)

        kwargs = {}
        for key, value in self._store.iteritems():
            kwargs[key] = value

        kwargs.update({"base_url": self._url_join(self._store["base_url"], item)})

        return Resource(**kwargs)

class Resource(ResourceCommon, object):
    def __init__(self, *args, **kwargs):
        self._store = kwargs

    def __call__(self, id=None):
        """
        Returns a new instance of self modified by one or more of the available
        parameters. These allows us to do things like override format for a
        specific request, and enables the api.resource(ID).get() syntax to get
        a specific resource by it's ID.
        """

        # Short Circuit out if the call is empty
        if id is None:
            return self

        kwargs = {}
        for key, value in self._store.iteritems():
            kwargs[key] = value

        if id is not None:
            kwargs["base_url"] = self._url_join(self._store["base_url"], id)

#        kwargs["session"] = self._store["session"]

        return self.__class__(**kwargs)

    def _print_debug(self, *args, **kwargs):
        if self._store["debug"]:
            print >> self._store["debug"], "DEBUG ",
            print >> self._store["debug"], kwargs['fmt'] % args

    def _extract_files(self, d):
        """
        Remove file-like objects from d and return them in a dictionary.
        """
        files = {}
        for k in d.keys():
            if callable(getattr(d[k], 'read', None)):
                files[k] = d[k]
                del d[k]
        return files

    def _debug_response(self, response):
        status = response.code
        reason = response.msg
        self._print_debug(status, reason, fmt="<< %s %s")
        for k,v in response.headers.items():
            self._print_debug(k,v, fmt="<< %s: %s")

    def _debug_request(self, request):
        try:
            self._print_debug(request._method,
                              request._Request__original,
                              fmt=">> %s %s")
        except AttributeError as e:
            self._print_debug("Request not found", fmt=">> %s")

        for k,v in request.headers.items():
            self._print_debug(k,v, fmt=">> %s: %s")

        self._print_debug(request.data, fmt=">> %s")


    def _request(self, method, data=None, params=None, files=None):
        url = self._store["base_url"]
        s = self._store["serializer"]
        auth = self._store["auth"]

        if self._store["append_slash"] and not url.endswith("/"):
            url += "/"

        params_encoded = urllib.urlencode(params)

        if params:
            url += '?' + params_encoded

        headers = {
            'accept': s.get_content_type()
        }

        try:
            if files:
                data['file'] = files['file']
                opener = urllib2.build_opener(MultipartPostHandler.MultipartPostHandler)
                response = opener.open(url.encode('ascii'), data)
            else:
                request = RequestWithMethod(method = method, url = url, data = data, headers=headers)
                request.add_header('Content-Type',  s.get_content_type())
                if auth:
                    request.add_header("Authorization", "Basic %s" % self._store["auth"].replace("\n",""))

                self._debug_request(request)
                response = urllib2.urlopen(request)
                self._debug_response(response)
        except urllib2.HTTPError as e:
            self._print_debug(e.read(), fmt="!! %s")
            raise HttpClientError(content = e.msg, code = e.code)
        except urllib2.URLError as e:
            self._print_debug(e.read(), fmt="!! %s")
            raise HttpServerError(content = e.reason)
        else:
            self._ = response
            return self._try_to_serialize_response(response)

    def _try_to_serialize_response(self, resp):

        s = self._store["serializer"]

        if resp.headers.get("content-type", None):
            content_type = resp.headers.get("content-type").split(";")[0].strip()

            try:
                stype = s.get_serializer(content_type=content_type)
            except SerializerNotAvailable:
                return resp.read()

            return stype.loads(resp.read())
        else:
            return resp.read()

    def get(self, **kwargs):
        return self._request("GET", params=kwargs)

    def post(self, data, **kwargs):
        s = self._store["serializer"]

        files = self._extract_files(data)
        # Files require data to be in a dictionary, not string
        if not files:
            data = s.dumps(data)

        ret = self._request("POST", data=data, params=kwargs, files=files)
        return ret

    def patch(self, data, **kwargs):
        s = self._store["serializer"]

#        resp = self._request("PATCH", data=s.dumps(data), params=kwargs)
        files = self._extract_files(data)
        # Files require data to be in a dictionary, not string
        if not files:
            data = s.dumps(data)

        return self._request("PUT", data=data, params=kwargs, files=files)

    def put(self, data, **kwargs):
        s = self._store["serializer"]
        return self._request("PUT", data=s.dumps(data), params=kwargs)

    def delete(self, **kwargs):
        resp = self._request("DELETE", params=kwargs)
        return True


class API(ResourceCommon, object):
    def __init__(self, base_url=None, auth=None, format=None, append_slash=True, serializer=None, debug=False):
        if serializer is None:
            s = Serializer(default=format)

        self._store = {
            "base_url": base_url,
            "format": format if format is not None else "json",
            "append_slash": append_slash,
            "debug": debug,
            "auth": base64.encodestring('%s:%s' % (auth[0], auth[1])) if auth is not None else None,
            "serializer": s,
        }

        # Do some Checks for Required Values
        if self._store.get("base_url") is None:
            print "base_url is required"
