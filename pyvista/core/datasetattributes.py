"""Implements DataSetAttributes, which represents & manipulates datasets."""

from vtk.numpy_interface.dataset_adapter import VTKObjectWrapper
import numpy
import pyvista.utilities.helpers as helpers
from .pyvista_ndarray import pyvista_ndarray
from pyvista.utilities.helpers import FieldAssociation
from vtk.numpy_interface.dataset_adapter import VTKObjectWrapper, numpyTovtkDataArray


class DataSetAttributes(VTKObjectWrapper):
    """
    Python friendly wrapper of vtk.DataSetAttributes.

    Implement a dict like interface for interacting with vtkDataArrays.

    Parameters
        ----------
        vtkobject : vtkFieldData
            The vtk object to wrap as a DataSetAttribute,
             usually an instance of vtkCellData, vtkPointData, vtkFieldData.

        dataset : vtkDataSet
            The vtkDataSet containing the vtkobject.

        association : FieldAssociation
            The array association type of the vtkobject.
    """

    def __init__(self, vtkobject, dataset, association):
        """Initialize DataSetAttributes."""
        super().__init__(vtkobject=vtkobject)
        self.dataset = dataset
        self.association = association

    def __getitem__(self, key):
        """
        Implement get behaviour of [] operator.

        Accepts an array name or an index.
        """
        return self.get_array(key)

    def __setitem__(self, key, value):
        """Implement setting behaviour of [] operator."""
        self.append(narray=value, name=key)

    def __delitem__(self, key):
        """Implement del."""
        self.remove(key)

    def __contains__(self, item):
        """Implement 'in' operator. Accepts a string array name."""
        return item in self.keys()

    def __iter__(self):
        """Implement for _ in self."""
        for array in self.keys():
            yield array

    def __len__(self):
        """Return the number of arrays."""
        return self.VTKObject.GetNumberOfArrays()

    @property
    def active_scalars(self):
        """Return the active scalar array as pyvista_ndarray."""
        self._raise_field_data_no_scalars_vectors()
        if self.GetScalars() is not None:
            return pyvista_ndarray.from_vtk_data_array(self.GetScalars(), dataset=self.dataset)

    @active_scalars.setter
    def active_scalars(self, name: str):
        """Set the active scalars by name."""
        self._raise_field_data_no_scalars_vectors()
        self.SetActiveScalars(name)

    @property
    def active_vectors(self):
        """Return the active scalar array as pyvista_ndarray."""
        self._raise_field_data_no_scalars_vectors()
        if self.GetVectors() is not None:
            return pyvista_ndarray.from_vtk_data_array(self.GetVectors(), dataset=self.dataset)

    @active_vectors.setter
    def active_vectors(self, name: str):
        """Set the active vectors by name."""
        self._raise_field_data_no_scalars_vectors()
        self.SetActiveVectors(name)

    @property
    def valid_array_len(self):
        """
        Return the length an ndarray should be when added to the dataset.

        If there are no restrictions, return None
        """
        if self.association == FieldAssociation.POINT:
            return self.dataset.GetNumberOfPoints()
        elif self.association == FieldAssociation.CELL:
            return self.dataset.GetNumberOfCells()
        return None

    @property
    def t_coords(self):
        """Return the active texture coordinates on the points."""
        t_coords = self.GetTCoords()
        if t_coords is not None:
            return pyvista_ndarray.from_vtk_data_array(t_coords)

    @t_coords.setter
    def t_coords(self, t_coords):
        """Set the array to use as the texture coordinates."""
        if not isinstance(t_coords, numpy.ndarray):
            raise TypeError('Texture coordinates must be a numpy array')
        if t_coords.ndim != 2:
            raise AssertionError('Texture coordinates must be a 2-dimensional array')
        valid_length = self.valid_array_len
        if t_coords.shape[0] != valid_length:
            raise AssertionError('Number of texture coordinates ({}) must match number of points ({})'.format(t_coords.shape[0], valid_length))
        if t_coords.shape[1] != 2:
            raise AssertionError('Texture coordinates must only have 2 components, not ({})'.format(t_coords.shape[1]))
        vtkarr = numpyTovtkDataArray(t_coords, name='Texture Coordinates')
        self.SetTCoords(vtkarr)
        self.Modified()

    def get_array(self, key):
        """Get an array in this instance.

        Parameters
        ----------
        key : str, index
            The name or index of the array to return.

        Returns
        ----------
        A pyvista_ndarray if the underlying array is a vtkDataArray,
        vtkAbstractArray if the former does not exist, or raises
        KeyError if neither exist.
        """
        self._raise_index_out_of_bounds(index=key)
        vtk_arr = self.VTKObject.GetArray(key)
        if not vtk_arr:
            vtk_arr = self.VTKObject.GetAbstractArray(key)
            if vtk_arr is None:
                raise KeyError('"{}"'.format(key))
            return vtk_arr
        narray = pyvista_ndarray.from_vtk_data_array(vtk_arr, dataset=self.dataset, association=self.association)
        if vtk_arr.GetName() in self.dataset.association_bitarray_names[self.association]:
            narray = narray.view(numpy.bool)
        return narray

    def append(self, narray, name, deep_copy=False):
        """Add an array to the data set attributes.

        Parameters
        ----------
        narray : array_like, scalar value
            A pyvista_ndarray, numpy.ndarray, list, tuple or scalar value.

        name : str
            Name of the array to add.

        deep_copy : bool
            When True makes a full copy of the array.

        """
        if narray is None:
            raise TypeError('narray cannot be None.')
        if isinstance(narray, (list, tuple)):
            narray = pyvista_ndarray.from_iter(narray)

        if self.association == FieldAssociation.POINT:
            array_len = self.dataset.GetNumberOfPoints()
        elif self.association == FieldAssociation.CELL:
            array_len = self.dataset.GetNumberOfCells()
        elif self.association == FieldAssociation.ROW:
            array_len = narray.shape[0]
        else:
            array_len = narray.shape[0] if isinstance(narray, numpy.ndarray) else 1

        # Fixup input array length for scalar input:
        if not isinstance(narray, numpy.ndarray) or numpy.ndim(narray) == 0:
            tmparray = numpy.empty(array_len)
            tmparray.fill(narray)
            narray = tmparray

        if narray.shape[0] != array_len:
            raise ValueError('narray length of ({}) != required length ({})'.format(
                narray.shape[0], array_len))

        if narray.dtype == numpy.bool:
            self.dataset.association_bitarray_names[self.association].add(name)
            narray = narray.view(numpy.uint8)

        shape = narray.shape
        if len(shape) == 3:
            # Array of matrices. We need to make sure the order  in memory is right.
            # If column order (c order), transpose. VTK wants row order (fortran
            # order). The deep copy later will make sure that the array is contiguous.
            # If row order but not contiguous, transpose so that the deep copy below
            # does not happen.
            size = narray.dtype.itemsize
            if (narray.strides[1] / size == 3 and narray.strides[2] / size == 1) or \
                (narray.strides[1] / size == 1 and narray.strides[2] / size == 3 and \
                 not narray.flags.contiguous):
                narray = narray.transpose(0, 2, 1)

        # If array is not contiguous, make a deep copy that is contiguous
        if not narray.flags.contiguous:
            narray = numpy.ascontiguousarray(narray)

        # Flatten array of matrices to array of vectors
        if len(shape) == 3:
            narray = narray.reshape(shape[0], shape[1]*shape[2])

        # Swap bytes from big to little endian.
        if narray.dtype.byteorder == '>':
            narray = narray.byteswap(inplace=True)

        # this handles the case when an input array is directly appended on the
        # output. We want to make sure that the array added to the output is not
        # referring to the input dataset.
        try:
            copy = pyvista_ndarray(narray, vtk_array=narray.VTKObject)
        except AttributeError:
            copy = pyvista_ndarray(narray)

        vtk_arr = helpers.convert_array(copy, name, deep=deep_copy)
        self.VTKObject.AddArray(vtk_arr)
        self.VTKObject.Modified()

    def remove(self, key):
        """Remove an array by key.

        Parameters
        ----------
        key : int, str
            The name or index of the array to remove.
        """
        self._raise_index_out_of_bounds(index=key)
        name = self.get_array(key).GetName()
        try:
            self.dataset.association_bitarray_names[self.association].remove(name)
        except KeyError:
            pass
        self.VTKObject.RemoveArray(key)
        self.VTKObject.Modified()

    def pop(self, key):
        """Remove an array by key and return it.

        Parameters
        ----------
        key : int, str
            The name or index of the array to remove.
        """
        self._raise_index_out_of_bounds(index=key)
        vtk_arr = self.GetArray(key)
        if vtk_arr:
            copy = vtk_arr.NewInstance()
            copy.DeepCopy(vtk_arr)
            vtk_arr = copy
        self.remove(key)
        return pyvista_ndarray.from_vtk_data_array(vtk_arr)

    def items(self):
        """Return a list of (array name, array value)."""
        return list(zip(self.keys(), self.values()))

    def keys(self):
        """Return the names of the arrays as a list."""
        keys = []
        for i in range(self.GetNumberOfArrays()):
            name = self.VTKObject.GetAbstractArray(i).GetName()
            if name:
                keys.append(name)
        return keys

    def values(self):
        """Return the arrays as a list."""
        values = []
        for i in range(self.GetNumberOfArrays()):
            array = self.VTKObject.GetAbstractArray(i)
            if array.GetName():
                values.append(pyvista_ndarray.from_vtk_data_array(array))
        return values

    def clear(self):
        """Remove all arrays in this instance."""
        for array_name in self.keys():
            self.remove(key=array_name)

    def update(self, array_dict):
        """Update arrays in this instance.

        For each key, value given, add the pair, if it already exists, update it.

        Parameters
        ----------
        array_dict : dict
            A dictionary of (array name, numpy.ndarray)
        """
        for name, array in array_dict.items():
            self[name] = array

    def _raise_index_out_of_bounds(self, index):
        max_index = self.VTKObject.GetNumberOfArrays()
        if isinstance(index, int):
            if index < 0 or index >= self.VTKObject.GetNumberOfArrays():
                raise KeyError('Array index ({}) out of range [0, {}]'.format(index, max_index))

    def _raise_field_data_no_scalars_vectors(self):
        if self.association == FieldAssociation.NONE:
            raise TypeError('vtkFieldData does not have active scalars or vectors.')
