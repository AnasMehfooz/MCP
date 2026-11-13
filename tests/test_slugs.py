import pytest

from store.slugs import slugify


@pytest.mark.parametrize(
    ("text", "slug"),
    [
        ("Black T-Shirt (M)", "black-t-shirt-m"),
        ("Bio T-Shirt (Größe M)", "bio-t-shirt-groesse-m"),
        ("Öl & Essig", "oel-essig"),
        ("  Crème brûlée  Set ", "creme-brulee-set"),
        ("!!!", "product"),
    ],
)
def test_slugify(text, slug):
    assert slugify(text, fallback="product") == slug


def test_slugify_never_ends_on_a_dash_when_cut():
    assert slugify("a" * 50 + " " + "b" * 50, fallback="x", max_length=51) == "a" * 50
