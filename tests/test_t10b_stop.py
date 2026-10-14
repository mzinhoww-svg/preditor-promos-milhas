"""T10b (1): arquivo/flag STOP faz job diario e coletor abortarem sem gravar."""
import pytest

from preditor.stop import StopRequested, check_stop


def test_check_stop_ok_sem_arquivo(tmp_path, monkeypatch):
    monkeypatch.setenv("PREDITOR_STOP_FILE", str(tmp_path / "STOP"))
    monkeypatch.delenv("PREDITOR_STOP", raising=False)
    check_stop()  # nao levanta


def test_check_stop_arquivo(tmp_path, monkeypatch):
    f = tmp_path / "STOP"
    f.write_text("")
    monkeypatch.setenv("PREDITOR_STOP_FILE", str(f))
    with pytest.raises(StopRequested):
        check_stop()


def test_check_stop_flag_env(tmp_path, monkeypatch):
    monkeypatch.setenv("PREDITOR_STOP_FILE", str(tmp_path / "STOP"))
    monkeypatch.setenv("PREDITOR_STOP", "1")
    with pytest.raises(StopRequested):
        check_stop()


class _Boom:
    """Engine que explode em qualquer uso: prova que nada foi lido nem gravado."""

    def __getattr__(self, name):
        raise AssertionError(f"engine tocado ({name}) com STOP presente")


@pytest.fixture
def stop_on(tmp_path, monkeypatch):
    f = tmp_path / "STOP"
    f.write_text("")
    monkeypatch.setenv("PREDITOR_STOP_FILE", str(f))


def test_run_daily_aborta_sem_gravar(stop_on):
    from preditor.jobs.daily_predict import run_daily

    with pytest.raises(StopRequested):
        run_daily(as_of="2026-06-01", engine=_Boom())


def test_collect_rss_aborta_sem_gravar(stop_on):
    from preditor.collector import collect_rss

    with pytest.raises(StopRequested):
        collect_rss(engine=_Boom(), source="x", url="http://x/feed")


def test_backfill_aborta_sem_gravar(stop_on):
    from preditor.collector import backfill

    with pytest.raises(StopRequested):
        backfill(engine=_Boom(), source="x", from_="202301")


def test_main_job_sai_com_codigo_3(stop_on):
    from preditor.jobs.daily_predict import main

    with pytest.raises(SystemExit) as e:
        main(["daily", "--as-of", "2026-06-01"])
    assert e.value.code == 3
