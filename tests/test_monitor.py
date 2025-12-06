from src.monitor import render_table, render_page


def test_render_table_and_page():
    html = render_table(["A", "B"], [[1, 2], ["x", "y"]])
    assert "<th>A</th>" in html
    assert "<td>1</td>" in html
    wrapped = render_page("Title", html)
    assert "Title" in wrapped
    assert html in wrapped
