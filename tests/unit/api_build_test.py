import gzip
import io
import shutil

import pytest

import docker
from docker import auth, errors
from docker.api.build import process_dockerfile

from ..helpers import make_tree
from .api_test import BaseAPIClientTest, fake_request, url_prefix


class BuildTest(BaseAPIClientTest):
    def test_build_container(self):
        script = io.BytesIO(
            "\n".join(
                [
                    "FROM busybox",
                    "RUN mkdir -p /tmp/test",
                    "EXPOSE 8080",
                    "ADD https://dl.dropboxusercontent.com/u/20637798/silence.tar.gz"
                    " /tmp/silence.tar.gz",
                ]
            ).encode("ascii")
        )

        self.client.build(fileobj=script)

    def test_build_container_with_stream_with_timestamp(self):
        script = io.BytesIO(
            "\n".join(
                [
                    "FROM busybox",
                    "RUN mkdir -p /tmp/test",
                    "EXPOSE 8080",
                    "ADD https://dl.dropboxusercontent.com/u/20637798/silence.tar.gz"
                    " /tmp/silence.tar.gz",
                ]
            ).encode("ascii")
        )

        self.client.build(fileobj=script, stream=True, timestamp=True)

    def test_build_container_pull(self):
        script = io.BytesIO(
            "\n".join(
                [
                    "FROM busybox",
                    "RUN mkdir -p /tmp/test",
                    "EXPOSE 8080",
                    "ADD https://dl.dropboxusercontent.com/u/20637798/silence.tar.gz"
                    " /tmp/silence.tar.gz",
                ]
            ).encode("ascii")
        )

        self.client.build(fileobj=script, pull=True)

    def test_build_container_custom_context(self):
        script = io.BytesIO(
            "\n".join(
                [
                    "FROM busybox",
                    "RUN mkdir -p /tmp/test",
                    "EXPOSE 8080",
                    "ADD https://dl.dropboxusercontent.com/u/20637798/silence.tar.gz"
                    " /tmp/silence.tar.gz",
                ]
            ).encode("ascii")
        )
        context = docker.utils.mkbuildcontext(script)

        self.client.build(fileobj=context, custom_context=True)

    def test_build_container_custom_context_gzip(self):
        script = io.BytesIO(
            "\n".join(
                [
                    "FROM busybox",
                    "RUN mkdir -p /tmp/test",
                    "EXPOSE 8080",
                    "ADD https://dl.dropboxusercontent.com/u/20637798/silence.tar.gz"
                    " /tmp/silence.tar.gz",
                ]
            ).encode("ascii")
        )
        context = docker.utils.mkbuildcontext(script)
        gz_context = gzip.GzipFile(fileobj=context)

        self.client.build(fileobj=gz_context, custom_context=True, encoding="gzip")

    def test_build_remote_with_registry_auth(self):
        self.client._auth_configs = auth.AuthConfig(
            {
                "auths": {
                    "https://example.com": {
                        "user": "example",
                        "password": "example",
                        "email": "example@example.com",
                    }
                }
            }
        )

        expected_params = {
            "t": None,
            "q": False,
            "dockerfile": None,
            "rm": False,
            "nocache": False,
            "pull": False,
            "forcerm": False,
            "remote": "https://github.com/docker-library/mongo",
        }
        expected_headers = {
            "X-Registry-Config": auth.encode_header(self.client._auth_configs.auths)
        }

        self.client.build(path="https://github.com/docker-library/mongo")

        fake_request.assert_called_with(
            "POST",
            f"{url_prefix}build",
            stream=True,
            data=None,
            headers=expected_headers,
            params=expected_params,
            timeout=None,
        )

    def test_build_container_with_named_dockerfile(self):
        self.client.build(".", dockerfile="nameddockerfile")

    def test_build_with_invalid_tag(self):
        with pytest.raises(errors.DockerException):
            self.client.build(".", tag="https://example.com")

    def test_build_container_with_container_limits(self):
        self.client.build(
            ".",
            container_limits={
                "memory": 1024 * 1024,
                "cpusetcpus": 1,
                "cpushares": 1000,
                "memswap": 1024 * 1024 * 8,
            },
        )

    def test_build_container_invalid_container_limits(self):
        with pytest.raises(docker.errors.DockerException):
            self.client.build(".", container_limits={"foo": "bar"})

    def test_set_auth_headers_with_empty_dict_and_auth_configs(self):
        self.client._auth_configs = auth.AuthConfig(
            {
                "auths": {
                    "https://example.com": {
                        "user": "example",
                        "password": "example",
                        "email": "example@example.com",
                    }
                }
            }
        )

        headers = {}
        expected_headers = {
            "X-Registry-Config": auth.encode_header(self.client._auth_configs.auths)
        }

        self.client._set_auth_headers(headers)
        assert headers == expected_headers

    def test_set_auth_headers_with_dict_and_auth_configs(self):
        self.client._auth_configs = auth.AuthConfig(
            {
                "auths": {
                    "https://example.com": {
                        "user": "example",
                        "password": "example",
                        "email": "example@example.com",
                    }
                }
            }
        )

        headers = {"foo": "bar"}
        expected_headers = {
            "X-Registry-Config": auth.encode_header(self.client._auth_configs.auths),
            "foo": "bar",
        }

        self.client._set_auth_headers(headers)
        assert headers == expected_headers

    def test_set_auth_headers_with_dict_and_no_auth_configs(self):
        headers = {"foo": "bar"}
        expected_headers = {"foo": "bar"}

        self.client._set_auth_headers(headers)
        assert headers == expected_headers

    @pytest.mark.skipif(
        not docker.constants.IS_WINDOWS_PLATFORM, reason="Windows-specific syntax"
    )
    def test_process_dockerfile_win_longpath_prefix(self):
        dirs = [
            "foo",
            "foo/bar",
            "baz",
        ]

        files = [
            "Dockerfile",
            "foo/Dockerfile.foo",
            "foo/bar/Dockerfile.bar",
            "baz/Dockerfile.baz",
        ]

        base = make_tree(dirs, files)
        self.addCleanup(shutil.rmtree, base)

        def pre(path):
            return docker.constants.WINDOWS_LONGPATH_PREFIX + path

        assert process_dockerfile(None, pre(base)) == (None, None)
        assert process_dockerfile("Dockerfile", pre(base)) == ("Dockerfile", None)
        assert process_dockerfile("foo/Dockerfile.foo", pre(base)) == (
            "foo/Dockerfile.foo",
            None,
        )
        assert process_dockerfile("../Dockerfile", pre(f"{base}\\foo"))[1] is not None
        assert process_dockerfile("../baz/Dockerfile.baz", pre(f"{base}/baz")) == (
            "../baz/Dockerfile.baz",
            None,
        )

    def test_process_dockerfile(self):
        dirs = [
            "foo",
            "foo/bar",
            "baz",
        ]

        files = [
            "Dockerfile",
            "foo/Dockerfile.foo",
            "foo/bar/Dockerfile.bar",
            "baz/Dockerfile.baz",
        ]

        base = make_tree(dirs, files)
        self.addCleanup(shutil.rmtree, base)

        assert process_dockerfile(None, base) == (None, None)
        assert process_dockerfile("Dockerfile", base) == ("Dockerfile", None)
        assert process_dockerfile("foo/Dockerfile.foo", base) == (
            "foo/Dockerfile.foo",
            None,
        )
        assert process_dockerfile("../Dockerfile", f"{base}/foo")[1] is not None
        assert process_dockerfile("../baz/Dockerfile.baz", f"{base}/baz") == (
            "../baz/Dockerfile.baz",
            None,
        )
