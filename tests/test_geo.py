from travelspark.geo import Bounds, project_to_pixel


def test_projection_places_center_near_middle():
    x, y = project_to_pixel(0.0, 0.0, bounds=Bounds(-10.0, -10.0, 10.0, 10.0), width=100, height=100)

    assert 45.0 <= x <= 55.0
    assert 45.0 <= y <= 55.0
