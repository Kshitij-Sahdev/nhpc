"""
KML parser unit tests.

Tests KML parsing, name cleaning, and coordinate downsampling.
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import update_forecasts


# Minimal valid KML for testing
SAMPLE_KML = """<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2">
  <Document>
    <name>TestCatchment.kml</name>
    <Placemark>
      <name>TestPlant</name>
      <Polygon>
        <outerBoundaryIs>
          <LinearRing>
            <coordinates>
              77.0,31.0,0
              77.1,31.0,0
              77.1,31.1,0
              77.0,31.1,0
              77.0,31.0,0
            </coordinates>
          </LinearRing>
        </outerBoundaryIs>
      </Polygon>
    </Placemark>
  </Document>
</kml>
"""

MULTI_PLANT_KML = """<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2">
  <Document>
    <name>MultiPlant.kml</name>
    <Placemark>
      <name>PlantAlpha</name>
      <Polygon>
        <outerBoundaryIs>
          <LinearRing>
            <coordinates>
              77.0,31.0,0
              77.1,31.0,0
              77.1,31.1,0
              77.0,31.1,0
              77.0,31.0,0
            </coordinates>
          </LinearRing>
        </outerBoundaryIs>
      </Polygon>
    </Placemark>
    <Placemark>
      <name>PlantBeta</name>
      <Polygon>
        <outerBoundaryIs>
          <LinearRing>
            <coordinates>
              93.0,28.0,0
              93.1,28.0,0
              93.1,28.1,0
              93.0,28.1,0
              93.0,28.0,0
            </coordinates>
          </LinearRing>
        </outerBoundaryIs>
      </Polygon>
    </Placemark>
  </Document>
</kml>
"""


class TestKMLParsing:
    """Tests for KML file parsing."""

    def test_parse_single_plant(self, tmp_path):
        """Should parse a single plant from KML."""
        kml_file = tmp_path / "test.kml"
        kml_file.write_text(SAMPLE_KML, encoding="utf-8")

        plants = update_forecasts.parse_kml(str(kml_file))
        assert len(plants) == 1
        assert plants[0]["name"] == "TestPlant"
        assert "lat" in plants[0]
        assert "lon" in plants[0]
        assert "boundaries" in plants[0]

    def test_parse_multiple_plants(self, tmp_path):
        """Should parse multiple plants from KML."""
        kml_file = tmp_path / "multi.kml"
        kml_file.write_text(MULTI_PLANT_KML, encoding="utf-8")

        plants = update_forecasts.parse_kml(str(kml_file))
        assert len(plants) == 2
        names = [p["name"] for p in plants]
        assert "PlantAlpha" in names
        assert "PlantBeta" in names

    def test_centroid_calculation(self, tmp_path):
        """Centroid should be the average of all coordinates."""
        kml_file = tmp_path / "centroid.kml"
        kml_file.write_text(SAMPLE_KML, encoding="utf-8")

        plants = update_forecasts.parse_kml(str(kml_file))
        plant = plants[0]
        # Centroid of (31.0, 77.0), (31.0, 77.1), (31.1, 77.1), (31.1, 77.0), (31.0, 77.0)
        # Average lat: (31.0 + 31.0 + 31.1 + 31.1 + 31.0) / 5 = 31.04
        # Average lon: (77.0 + 77.1 + 77.1 + 77.0 + 77.0) / 5 = 77.04
        assert abs(plant["lat"] - 31.04) < 0.01
        assert abs(plant["lon"] - 77.04) < 0.01

    def test_missing_kml_raises_error(self):
        """Parsing a non-existent file should raise KMLParseError."""
        from exceptions import KMLParseError
        with pytest.raises(KMLParseError):
            update_forecasts.parse_kml("/nonexistent/path/file.kml")

    def test_plants_have_sequential_ids(self, tmp_path):
        """Plant IDs should be sequential starting from 1."""
        kml_file = tmp_path / "ids.kml"
        kml_file.write_text(MULTI_PLANT_KML, encoding="utf-8")

        plants = update_forecasts.parse_kml(str(kml_file))
        ids = [p["id"] for p in plants]
        assert ids == [1, 2]


class TestCleanName:
    """Tests for the clean_name function."""

    def test_known_mappings(self):
        """Known abbreviations should be resolved."""
        assert update_forecasts.clean_name("TanakpurCorrected", "doc.kml") == "Tanakpur HEP"
        assert update_forecasts.clean_name("nbpdam", "doc.kml") == "Nimoo Bazgo HEP"
        assert update_forecasts.clean_name("ChutakPS", "doc.kml") == "Chutak Power Station"
        assert update_forecasts.clean_name("Uri_I", "doc.kml") == "Uri-I Power Station"
        assert update_forecasts.clean_name("Uri_II", "doc.kml") == "Uri-II Power Station"

    def test_underscores_to_spaces(self):
        """Underscores in names should be converted to spaces."""
        result = update_forecasts.clean_name("Some_Plant_Name", "doc.kml")
        assert "_" not in result
        assert "Some Plant Name" == result

    def test_none_name_uses_doc(self):
        """None placemark name should fall back to document name."""
        result = update_forecasts.clean_name(None, "Chamera-I.kml")
        assert result == "Chamera-I HEP"

    def test_unnamed_uses_doc(self):
        """'Unnamed' should fall back to document name."""
        result = update_forecasts.clean_name("Unnamed", "Parbati-III.kml")
        assert result == "Parbati-III HEP"

    def test_disambiguation_project(self):
        """Kishanganga in KML should get (Project) suffix."""
        result = update_forecasts.clean_name("Kishanganga", "test.kml")
        assert result == "Kishanganga HEP (Project)"

    def test_disambiguation_catchment(self):
        """Kishanganga in SHP should get (Catchment) suffix."""
        result = update_forecasts.clean_name("Kishanganga", "test.shp")
        assert result == "Kishanganga HEP (Catchment)"


class TestDownsampleCoordinates:
    """Tests for coordinate downsampling."""

    def test_small_list_unchanged(self):
        """Lists smaller than max_points should not be modified."""
        coords = [[1.0, 2.0], [3.0, 4.0], [5.0, 6.0]]
        result = update_forecasts.downsample_coordinates(coords, max_points=100)
        assert result == coords

    def test_large_list_downsampled(self):
        """Large lists should be reduced to approximately max_points."""
        coords = [[float(i), float(i)] for i in range(1000)]
        result = update_forecasts.downsample_coordinates(coords, max_points=50)
        assert len(result) <= 55  # Allow slight overshoot for closure

    def test_closure_preserved(self):
        """If original is a closed polygon, result should be closed."""
        coords = [[0.0, 0.0], [1.0, 0.0], [1.0, 1.0], [0.0, 1.0]] * 50
        coords.append([0.0, 0.0])  # Close the polygon
        result = update_forecasts.downsample_coordinates(coords, max_points=10)
        assert result[0] == result[-1]
