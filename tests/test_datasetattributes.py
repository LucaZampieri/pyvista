import numpy as np
from pytest import fixture, mark, raises
import pyvista
from vtk.numpy_interface.dataset_adapter import ArrayAssociation


@fixture()
def example_grid():
    return pyvista.UnstructuredGrid(pyvista.examples.hexbeamfile).copy()


@fixture()
def example_grid_point_attributes(example_grid):
    return example_grid.point_arrays


@fixture()
def insert_arange_narray(example_grid_point_attributes):
    n_points = example_grid_point_attributes.dataset.GetNumberOfPoints()
    sample_array = np.arange(n_points)
    example_grid_point_attributes.append(sample_array, 'sample_array')
    return example_grid_point_attributes, sample_array


def test_init(example_grid):
    attributes = pyvista.DataSetAttributes(
        example_grid.GetPointData(), dataset=example_grid, association=ArrayAssociation.POINT)
    assert attributes.VTKObject == example_grid.GetPointData()
    assert attributes.dataset == example_grid
    assert attributes.association == ArrayAssociation.POINT


class TestGetArray:
    def test_should_fail_if_does_not_exist(self, example_grid_point_attributes):
        with raises(KeyError):
            example_grid_point_attributes.get_array('invalid_array_name')
        with raises(KeyError):
            example_grid_point_attributes.get_array(-1)


class TestAdd:
    def test_append_should_not_add_none_array(self, example_grid_point_attributes):
        with raises(TypeError):
            example_grid_point_attributes.append(None, 'sample_array')

    def test_append_should_contain_array_name(self, insert_arange_narray):
        dsa, _ = insert_arange_narray
        assert 'sample_array' in dsa

    def test_append_should_contain_exact_array(self, insert_arange_narray):
        dsa, sample_array = insert_arange_narray
        assert np.array_equal(sample_array, dsa['sample_array'])

    def test_getters_should_return_same_result(self, insert_arange_narray):
        dsa, sample_array = insert_arange_narray
        result_a = dsa.get_array('sample_array')
        result_b = dsa['sample_array']
        assert np.array_equal(result_a, result_b)


class TestRemove:
    def test_should_remove_array(self, insert_arange_narray):
        dsa, sample_array = insert_arange_narray
        dsa.remove('sample_array')
        assert 'sample_array' not in dsa

    def test_should_del_array(self, insert_arange_narray):
        dsa, sample_array = insert_arange_narray
        del dsa['sample_array']
        assert 'sample_array' not in dsa

    def test_should_pop_array(self, insert_arange_narray):
        dsa, sample_array = insert_arange_narray
        dsa.pop('sample_array')
        assert 'sample_array' not in dsa

    @mark.parametrize('removed_key', [None, 'nonexistant_array_name', '', -1])
    def test_remove_should_fail_on_bad_argument(self, removed_key, example_grid_point_attributes):
        with raises(KeyError):
            example_grid_point_attributes.remove(removed_key)

    @mark.parametrize('removed_key', [None, 'nonexistant_array_name', '', -1])
    def test_del_should_fail_bad_argument(self, removed_key, example_grid_point_attributes):
        with raises(KeyError):
            del example_grid_point_attributes[removed_key]

    @mark.parametrize('removed_key', [None, 'nonexistant_array_name', '', -1])
    def test_pop_should_fail_bad_argument(self, removed_key, example_grid_point_attributes):
        with raises(KeyError):
            example_grid_point_attributes.pop(removed_key)


class TestLength:
    def test_should_increase_on_add(self, example_grid_point_attributes):
        initial_len = len(example_grid_point_attributes)
        n_points = example_grid_point_attributes.dataset.GetNumberOfPoints()
        sample_array = np.arange(n_points)
        example_grid_point_attributes.append(sample_array, 'sample_array')
        assert len(example_grid_point_attributes) == initial_len + 1

    def test_should_decrease_on_remove(self, insert_arange_narray):
        dsa, sample_array = insert_arange_narray
        initial_len = len(dsa)
        dsa.remove('sample_array')
        assert len(dsa) == initial_len - 1

    def test_should_be_0_on_clear(self, insert_arange_narray):
        dsa, sample_array = insert_arange_narray
        assert len(dsa) != 0
        dsa.clear()
        assert len(dsa) == 0


class TestKeys:
    def test_should_be_strings(self, insert_arange_narray):
        dsa, sample_array = insert_arange_narray
        for name in dsa.keys():
            assert(type(name) == str)

    def test_should_exist(self, insert_arange_narray):
        dsa, sample_array = insert_arange_narray
        assert 'sample_array' in dsa.keys()


class TestValues:
    def test_should_be_pyvista_ndarrays(self, insert_arange_narray):
        dsa, sample_array = insert_arange_narray
        for arr in dsa.values():
            assert(type(arr) == pyvista.pyvista_ndarray)

    def test_should_exist(self, insert_arange_narray):
        dsa, sample_array = insert_arange_narray
        for arr in dsa.values():
            if np.array_equal(sample_array, arr):
                return
        raise AssertionError('Array not in values.')