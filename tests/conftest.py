import pytest
import os


@pytest.fixture(scope="module")
def test_output_dir():
    out_dir = os.path.join(os.getcwd(), "tests/test_output")
    return out_dir
