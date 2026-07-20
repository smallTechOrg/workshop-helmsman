import pytest


@pytest.mark.parametrize(
    ("path", "target"),
    [
        ("/", "/app/"),
        ("/j/Ab3dEfGh", "/app/join/?s=Ab3dEfGh"),
        ("/p/some-participant-token", "/app/p/?t=some-participant-token"),
        ("/f/some-admin-token", "/app/f/?t=some-admin-token"),
    ],
)
def test_pretty_redirects_are_307_to_exact_targets(client, path, target):
    response = client.get(path, follow_redirects=False)
    assert response.status_code == 307
    assert response.headers["location"] == target
