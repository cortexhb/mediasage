"""Tests for ``GET /api/health``."""

from unittest.mock import patch

import pytest

from tests.api.conftest import mediasage_config


class TestHealth:
    def test_reports_healthy(self, client, plex):
        with patch("backend.config.store.ConfigStore.get", return_value=mediasage_config()):
            response = client.get("/api/health")

        assert response.status_code == 200
        assert response.json()["status"] == "healthy"

    def test_reports_a_connected_plex(self, client, plex):
        with patch("backend.config.store.ConfigStore.get", return_value=mediasage_config()):
            response = client.get("/api/health")

        assert response.json()["plex_connected"] is True

    @pytest.mark.parametrize("plex", [None], indirect=True)
    def test_reports_a_missing_plex(self, client, plex):
        """Health answers even with nothing configured; that is the point of it."""
        with patch("backend.config.store.ConfigStore.get", return_value=mediasage_config()):
            response = client.get("/api/health")

        assert response.status_code == 200
        assert response.json()["plex_connected"] is False

    def test_reports_a_configured_llm(self, client, plex):
        config = mediasage_config(llm_api_key="key")
        with patch("backend.config.store.ConfigStore.get", return_value=config):
            response = client.get("/api/health")

        assert response.json()["llm_configured"] is True

    def test_a_cloud_provider_without_a_key_is_unconfigured(self, client, plex):
        config = mediasage_config(llm_api_key="")
        with patch("backend.config.store.ConfigStore.get", return_value=config):
            response = client.get("/api/health")

        assert response.json()["llm_configured"] is False

    def test_a_local_provider_is_configured_by_its_url(self, client, plex):
        """Ollama and custom endpoints are reached by URL and need no key."""
        config = mediasage_config(llm_provider="ollama", llm_api_key="")
        with patch("backend.config.store.ConfigStore.get", return_value=config):
            response = client.get("/api/health")

        assert response.json()["llm_configured"] is True
