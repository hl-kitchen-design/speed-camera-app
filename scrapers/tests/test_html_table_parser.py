import os
import sys
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from html_table_parser import fetch_html_table_rows

SAMPLE_HTML_SINGLE_TABLE = """
<html><body>
<table>
<tr><th>地　點</th><th>違規取締項目</th><th>經度</th><th>緯度</th></tr>
<tr><td>新竹市北區經國路二段口</td><td>闖紅燈、違規轉彎</td><td>120.964470</td><td>24.811973</td></tr>
<tr><td>新竹市東區經國路一段口</td><td>闖紅燈</td><td>120.985230</td><td>24.815077</td></tr>
</table>
</body></html>
"""

SAMPLE_HTML_MULTIPLE_TABLES_SAME_HEADER = """
<html><body>
<p>違規停車自動偵測系統設置地點</p>
<table>
<tr><td>編號</td><td>設置位置</td><td>取締項目</td></tr>
<tr><td>1</td><td>板橋區縣民大道二段7號</td><td>違規(臨時)停車</td></tr>
</table>
<p>跨越雙黃線自動偵測系統設置地點</p>
<table>
<tr><td>編號</td><td>設置位置</td><td>取締項目</td></tr>
<tr><td>1</td><td>省道台2線85.8K</td><td>跨越雙黃線</td></tr>
<tr><td>2</td><td>省道台2線87.5K</td><td>跨越雙黃線</td></tr>
</table>
</body></html>
"""


def _mock_response(html: str):
    resp = MagicMock()
    resp.text = html
    resp.raise_for_status = MagicMock()
    return resp


def test_fetch_html_table_rows_normalizes_fullwidth_space_in_header():
    with patch("html_table_parser.requests.get", return_value=_mock_response(SAMPLE_HTML_SINGLE_TABLE)):
        rows = fetch_html_table_rows(
            "https://example.com", expected_header=["地點", "違規取締項目", "經度", "緯度"]
        )
    assert len(rows) == 2
    assert rows[0]["地點"] == "新竹市北區經國路二段口"
    assert rows[0]["經度"] == "120.964470"


def test_fetch_html_table_rows_merges_multiple_tables_with_same_header():
    with patch("html_table_parser.requests.get", return_value=_mock_response(SAMPLE_HTML_MULTIPLE_TABLES_SAME_HEADER)):
        rows = fetch_html_table_rows(
            "https://example.com", expected_header=["編號", "設置位置", "取締項目"]
        )
    assert len(rows) == 3
    assert rows[0]["設置位置"] == "板橋區縣民大道二段7號"
    assert rows[2]["設置位置"] == "省道台2線87.5K"


def test_fetch_html_table_rows_passes_verify_flag_to_requests():
    with patch("html_table_parser.requests.get", return_value=_mock_response(SAMPLE_HTML_SINGLE_TABLE)) as mock_get:
        fetch_html_table_rows(
            "https://example.com",
            expected_header=["地點", "違規取締項目", "經度", "緯度"],
            verify_ssl=False,
        )
    assert mock_get.call_args.kwargs["verify"] is False
