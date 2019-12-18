"""Unit tests for the module :mod:`esmvaltool.diag_scripts.mlr`."""

import os

import iris
import mock
import numpy as np
import pandas as pd
import pytest
from cf_units import Unit

from esmvaltool.diag_scripts import mlr
from esmvaltool.diag_scripts.mlr.models import MLRModel


@mock.patch('esmvaltool.diag_scripts.mlr.models.importlib', autospec=True)
@mock.patch('esmvaltool.diag_scripts.mlr.os.walk', autospec=True)
@mock.patch('esmvaltool.diag_scripts.mlr.os.path.dirname', autospec=True)
def test_load_mlr_models(mock_dirname, mock_walk, mock_importlib):
    """Test for loading mlr models."""
    root_dir = '/root/to/something'
    models = [
        (root_dir, ['dir', '__pycache__'], ['test.py', '__init__.py']),
        (os.path.join(root_dir, 'root2'), ['d'], ['__init__.py', '42.py']),
        (os.path.join(root_dir, 'root3'), [], []),
        (os.path.join(root_dir, 'root4'), ['d2'], ['egg.py']),
    ]
    mock_dirname.return_value = root_dir
    mock_walk.return_value = models
    MLRModel._load_mlr_models()
    modules = [
        'esmvaltool.diag_scripts.mlr.models.{}'.format(mod) for mod in
        ['test', '__init__', 'root2.__init__', 'root2.42', 'root4.egg']
    ]
    calls = [mock.call(module) for module in modules]
    mock_importlib.import_module.assert_has_calls(calls)


DF_1 = pd.DataFrame({'a': np.arange(5.0) - 2.0})
DF_1_OUT = pd.DataFrame({'a': [-2.0, 0.0, 2.0]})
DF_2 = pd.DataFrame({'b': [1.0, np.nan, 42.0, np.nan, 3.14]})
DF_2_OUT = pd.DataFrame({'b': [1.0, 42.0, 3.14]})
DF_3 = pd.DataFrame({'c': np.arange(5.0) + 1.0, 'd': np.arange(5.0) - 2.0})
DF_3_OUT = pd.DataFrame({'c': [1.0, 3.0, 5.0], 'd': [-2.0, 0.0, 2.0]})
TEST_REMOVE_MISSING_LABELS = [
    ([DF_1, DF_1, None], [DF_1, DF_1, None], 0),
    ([DF_1, DF_2, None], [DF_1_OUT, DF_2_OUT, None], 2),
    ([DF_2, DF_1, None], [DF_2, DF_1, None], 0),
    ([DF_2, DF_2, None], [DF_2_OUT, DF_2_OUT, None], 2),
    ([DF_3, DF_1, None], [DF_3, DF_1, None], 0),
    ([DF_3, DF_2, None], [DF_3_OUT, DF_2_OUT, None], 2),
    ([DF_1, DF_1, DF_1], [DF_1, DF_1, DF_1], 0),
    ([DF_1, DF_2, DF_1], [DF_1_OUT, DF_2_OUT, DF_1_OUT], 2),
    ([DF_2, DF_1, DF_2], [DF_2, DF_1, DF_2], 0),
    ([DF_2, DF_2, DF_2], [DF_2_OUT, DF_2_OUT, DF_2_OUT], 2),
    ([DF_3, DF_1, DF_1], [DF_3, DF_1, DF_1], 0),
    ([DF_3, DF_2, DF_1], [DF_3_OUT, DF_2_OUT, DF_1_OUT], 2),
]


@pytest.mark.parametrize('df_in,df_out,logger', TEST_REMOVE_MISSING_LABELS)
@mock.patch('esmvaltool.diag_scripts.mlr.models.logger', autospec=True)
def test_remove_missing_labels(mock_logger, df_in, df_out, logger):
    """Test removing of missing label data."""
    out = MLRModel._remove_missing_labels(*df_in)
    assert out is not df_in
    for (idx, df) in enumerate(df_out):
        if df is None:
            assert out[idx] is None
        else:
            assert df.equals(out[idx])
    if logger:
        assert logger in mock_logger.info.call_args[0]
    else:
        mock_logger.info.assert_not_called()


STEPS_1 = [('a', 1)]
STEPS_2 = [('a', 1), ('b', 0)]
TEST_GET_FIT_PARAMETERS = [
    ({'a': 1}, STEPS_1, ValueError),
    ({'a': 1, 'a__b': 1}, STEPS_1, ValueError),
    ({'a__x': 1}, [], ValueError),
    ({'a__x': 1}, STEPS_1, {'a': {'x': 1}}),
    ({'a__x': 1, 'a__y': 2}, STEPS_1, {'a': {'x': 1, 'y': 2}}),
    ({'a__x': 1, 'a__y__z': 2}, STEPS_1, {'a': {'x': 1, 'y__z': 2}}),
    ({'a__x': 1, 'b__y': 2}, STEPS_1, ValueError),
    ({'a__x': 1, 'b__y': 2}, STEPS_2, {'a': {'x': 1}, 'b': {'y': 2}}),
]


@pytest.mark.parametrize('kwargs,steps,output', TEST_GET_FIT_PARAMETERS)
def test_get_fit_parameters(kwargs, steps, output):
    """Test retrieving of fit parameters."""
    if isinstance(output, type):
        with pytest.raises(output):
            mlr._get_fit_parameters(kwargs, steps, 'x')
        return
    params = mlr._get_fit_parameters(kwargs, steps, 'x')
    assert params == output


TEST_CHECK_PREDICT_KWARGS = [
    ({'a': 1}, True),
    ({'return_var': False}, True),
    ({'return_var': False, 'a': 1}, True),
    ({'return_var': True, 'a': 1}, True),
    ({'return_cov': False}, True),
    ({'return_cov': False, 'a': 1}, True),
    ({'return_cov': True, 'a': 1}, True),
    ({'return_var': True, 'return_cov': False}, True),
    ({'return_var': True, 'return_cov': False, 'a': 1}, True),
    ({'return_var': False, 'return_cov': True}, True),
    ({'return_var': False, 'return_cov': True, 'a': 1}, True),
    ({'return_var': True, 'return_cov': True}, RuntimeError),
    ({'return_var': True, 'return_cov': True, 'a': 1}, RuntimeError),
]


@pytest.mark.parametrize('kwargs,output', TEST_CHECK_PREDICT_KWARGS)
def test_check_predict_kwargs(kwargs, output):
    """Test for check of predict kwargs."""
    if isinstance(output, type):
        with pytest.raises(output):
            mlr.check_predict_kwargs(kwargs)
        return
    assert mlr.check_predict_kwargs(kwargs) is None


TEST_UNITS_POWER = [
    (Unit('m'), 2.5, TypeError, False),
    (Unit(''), 1, ValueError, True),
    (Unit('no unit'), 1, ValueError, True),
    (Unit('2.0 m s-1'), 3, Unit('2.0 m s-1')**3, True),
    (Unit('m')**2, 2, Unit('m')**4, True),
    (Unit('m')**2, 0, Unit('m')**0, True),
    (Unit('m')**2, -3, Unit('m')**-6, True),
    (Unit('m'), 2, Unit('m2'), False),
    (Unit('m'), 0, Unit('m0'), False),
    (Unit('m'), -3, Unit('m-3'), False),
    (Unit('kg m'), 2, Unit('kg2 m2'), False),
    (Unit('kg m'), 0, Unit('kg0 m0'), False),
    (Unit('kg m'), -3, Unit('kg-3 m-3'), False),
    (Unit('kg.m'), 2, Unit('kg2 m2'), False),
    (Unit('kg.m'), 0, Unit('kg0 m0'), False),
    (Unit('kg.m'), -3, Unit('kg-3 m-3'), False),
    (Unit('kg m2'), 2, Unit('kg2 m4'), False),
    (Unit('kg m2'), 0, Unit('kg0 m0'), False),
    (Unit('kg m2'), -3, Unit('kg-3 m-6'), False),
    (Unit('kg.m2'), 2, Unit('kg2 m4'), False),
    (Unit('kg.m2'), 0, Unit('kg0 m0'), False),
    (Unit('kg.m2'), -3, Unit('kg-3 m-6'), False),
    (Unit('kg80 m-10'), 2, Unit('kg160 m-20'), False),
    (Unit('kg80 m-10'), 0, Unit('kg0 m0'), False),
    (Unit('kg80 m-10'), -3, Unit('kg-240 m30'), False),
    (Unit('kg80.m-10'), 2, Unit('kg160 m-20'), False),
    (Unit('kg80.m-10'), 0, Unit('kg0 m0'), False),
    (Unit('kg80.m-10'), -3, Unit('kg-240 m30'), False),
    (Unit('W m-2 K-1'), 2, Unit('W2 m-4 K-2'), False),
    (Unit('W m-2 K-1'), 0, Unit('W0 m0 K0'), False),
    (Unit('W m-2 K-1'), -3, Unit('W-3 m6 K3'), False),
    (Unit('W m-2.K-1'), 2, Unit('W2 m-4 K-2'), False),
    (Unit('W m-2.K-1'), 0, Unit('W0 m0 K0'), False),
    (Unit('W m-2.K-1'), -3, Unit('W-3 m6 K3'), False),
    (Unit('kg yr-1'), 2, Unit('kg2 yr-2'), False),
    (Unit('kg yr-1'), 0, Unit('kg0 yr0'), False),
    (Unit('kg yr-1'), -3, Unit('kg-3 yr3'), False),
    (Unit('kg.yr-1'), 2, Unit('kg2 yr-2'), False),
    (Unit('kg.yr-1'), 0, Unit('kg0 yr0'), False),
    (Unit('kg.yr-1'), -3, Unit('kg-3 yr3'), False),
]


@pytest.mark.parametrize('units_in,power,output,logger', TEST_UNITS_POWER)
@mock.patch.object(mlr, 'logger', autospec=True)
def test_units_power(mock_logger, units_in, power, output, logger):
    """Test exponentiation of :mod:`cf_units.Unit`."""
    if isinstance(output, type):
        with pytest.raises(output):
            mlr.units_power(units_in, power)
        return
    new_units = mlr.units_power(units_in, power)
    assert new_units == output
    assert new_units.origin == output.origin
    if logger:
        mock_logger.warning.assert_called_once()
    else:
        mock_logger.warning.assert_not_called()


DATASET = {
    'dataset': 'TEST',
    'exp': 'iceage',
    'filename': 'path/to/file',
    'project': 'CMIP4',
}
TEST_CREATE_ALIAS = [
    ([], None, ValueError),
    ([], 'x', ValueError),
    (['no'], None, AttributeError),
    (['no'], 'x', AttributeError),
    (['dataset'], None, 'TEST'),
    (['dataset'], 'x', 'TEST'),
    (['dataset', 'project'], None, 'TEST-CMIP4'),
    (['dataset', 'project'], 'x', 'TESTxCMIP4'),
]


@pytest.mark.parametrize('attrs,delim,output', TEST_CREATE_ALIAS)
def test_create_alias(attrs, delim, output):
    """Test alias creation."""
    kwargs = {}
    if delim is not None:
        kwargs['delimiter'] = delim
    if isinstance(output, type):
        with pytest.raises(output):
            mlr.create_alias(DATASET, attrs, **kwargs)
        return
    alias = mlr.create_alias(DATASET, attrs, **kwargs)
    assert alias == output


METADATA_IN = [iris.cube.CubeMetadata(*x) for x in [
    ('air_temperature', 'Long', 'var', 'kg2', {}, None),
    ('air_temperature', 'squared Long', 'var', 'kg2', {'squared': 1}, None),
    ('air_temperature', 'Squared Long', 'var', 'kg2', {}, None),
    ('air_temperature', 'squaredLong', 'var', 'kg2', {'squared': 1}, None),
    ('air_temperature', 'SquaredLong', 'var', 'kg2', {}, None),
    ('air_temperature', 'Long squared', 'var', 'kg2', {}, None),
    ('air_temperature', 'Long Squared', 'var', 'kg2', {'squared': 1}, None),
    ('air_temperature', 'Long (squared)', 'var', 'kg2', {}, None),
    ('air_temperature', 'Long (Squared)', 'var', 'kg2', {}, None),
    ('air_temperature', 'Long (squared test)', 'var', 'kg2', {}, None),
    ('air_temperature', 'Long (Squared test)', 'var', 'kg2', {}, None),
    ('air_temperature', 'squared Long (squared)', 'var', 'kg2', {}, None),
    ('air_temperature', 'Squared Long (Squared)', 'var', 'kg2', {}, None),
    ('air_temperature', 'Long squared', 'squared_var', 'kg2', {}, None),
    ('air_temperature', 'Long Squared', 'var_squared', 'kg2', {}, None),
    ('air_temperature', 'Long', 'squared_var_squared', 'kg2', {}, None),
]]
METADATA_OUT = [iris.cube.CubeMetadata(*x) for x in [
    ('air_temperature', 'Root Long', 'root_var', 'kg', {}, None),
    ('air_temperature', 'Long', 'root_var', 'kg', {}, None),
    ('air_temperature', 'Long', 'root_var', 'kg', {}, None),
    ('air_temperature', 'Root squaredLong', 'root_var', 'kg', {}, None),
    ('air_temperature', 'Root SquaredLong', 'root_var', 'kg', {}, None),
    ('air_temperature', 'Long', 'root_var', 'kg', {}, None),
    ('air_temperature', 'Long', 'root_var', 'kg', {}, None),
    ('air_temperature', 'Long', 'root_var', 'kg', {}, None),
    ('air_temperature', 'Long', 'root_var', 'kg', {}, None),
    ('air_temperature', 'Long (test)', 'root_var', 'kg', {}, None),
    ('air_temperature', 'Long (test)', 'root_var', 'kg', {}, None),
    ('air_temperature', 'Long (squared)', 'root_var', 'kg', {}, None),
    ('air_temperature', 'Long (Squared)', 'root_var', 'kg', {}, None),
    ('air_temperature', 'Long', 'var', 'kg', {}, None),
    ('air_temperature', 'Long', 'var', 'kg', {}, None),
    ('air_temperature', 'Root Long', 'var_squared', 'kg', {}, None),
]]
TEST_SQUARE_ROOT_METADATA = [
    (iris.cube.Cube(0, **METADATA_IN[idx]._asdict()),
     iris.cube.Cube(0, **METADATA_OUT[idx]._asdict())) for idx in
    range(len(METADATA_IN))
]


@pytest.mark.parametrize('cube_in,cube_out', TEST_SQUARE_ROOT_METADATA)
def test_square_root_metadata(cube_in, cube_out):
    """Test taking square root of cube metadata."""
    assert cube_in != cube_out
    assert cube_in is not cube_out
    mlr.square_root_metadata(cube_in)
    assert cube_in == cube_out


LONG_NAME_1 = 'long_name_1'
LONG_NAME_2 = 'long_name_2'
AUX_NAME = 'aux_name'
COORD_1 = iris.coords.DimCoord([-2.0, -1.0, 20.0], long_name=LONG_NAME_1)
COORD_2 = iris.coords.DimCoord([-2.0, -1.0, 20.0], long_name=LONG_NAME_2)
COORD_3 = iris.coords.DimCoord([-42.0], long_name=LONG_NAME_2)
COORD_AUX = iris.coords.AuxCoord(['a', 'b', 'c'], long_name=AUX_NAME)
CUBE_1 = iris.cube.Cube(np.arange(3.0), dim_coords_and_dims=[(COORD_1, 0)])
CUBE_2 = iris.cube.Cube(np.arange(3.0), dim_coords_and_dims=[(COORD_2, 0)])
CUBE_3 = iris.cube.Cube(np.arange(1.0), dim_coords_and_dims=[(COORD_3, 0)])
CUBE_4 = iris.cube.Cube(np.arange(3.0),
                        dim_coords_and_dims=[(COORD_1, 0)],
                        aux_coords_and_dims=[(COORD_AUX, 0)])
CUBE_5 = iris.cube.Cube(np.arange(3.0 * 3.0).reshape(3, 3),
                        dim_coords_and_dims=[(COORD_1, 0), (COORD_2, 1)],
                        aux_coords_and_dims=[(COORD_AUX, 0)])
CUBE_6 = iris.cube.Cube(np.arange(3.0).reshape(1, 3),
                        dim_coords_and_dims=[(COORD_3, 0), (COORD_1, 1)])
TEST_CHECK_COORDS = [
    (CUBE_1, [LONG_NAME_1], True),
    (CUBE_2, [LONG_NAME_1], False),
    (CUBE_3, [LONG_NAME_1], False),
    (CUBE_4, [LONG_NAME_1], True),
    (CUBE_5, [LONG_NAME_1], True),
    (CUBE_6, [LONG_NAME_1], True),
    (CUBE_1, [LONG_NAME_1, LONG_NAME_2], False),
    (CUBE_2, [LONG_NAME_1, LONG_NAME_2], False),
    (CUBE_3, [LONG_NAME_1, LONG_NAME_2], False),
    (CUBE_4, [LONG_NAME_1, LONG_NAME_2], False),
    (CUBE_5, [LONG_NAME_1, LONG_NAME_2], True),
    (CUBE_6, [LONG_NAME_1, LONG_NAME_2], False),
    (CUBE_1, [LONG_NAME_1, LONG_NAME_2, AUX_NAME], False),
    (CUBE_2, [LONG_NAME_1, LONG_NAME_2, AUX_NAME], False),
    (CUBE_3, [LONG_NAME_1, LONG_NAME_2, AUX_NAME], False),
    (CUBE_4, [LONG_NAME_1, LONG_NAME_2, AUX_NAME], False),
    (CUBE_5, [LONG_NAME_1, LONG_NAME_2, AUX_NAME], True),
    (CUBE_6, [LONG_NAME_1, LONG_NAME_2, AUX_NAME], False),
]


@pytest.mark.parametrize('cube,coords,output', TEST_CHECK_COORDS)
def test_has_valid_coords(cube, coords, output):
    """Test check for valid coords."""
    out = mlr._has_valid_coords(cube, coords)
    assert out == output


D_1 = {
    'dataset': 'c',
    'filename': 'b',
    'long_name': 'e',
    'project': 'a',
    'short_name': 'd',
    'tag': 'g',
    'var_name': 'f',
    'var_type': 'label',
    'units': 'kg',
}
D_2 = D_1.copy()
D_2.pop('project')
D_2['short_name'] = 'xx'
D_3 = D_1.copy()
D_3['var_type'] = 'wrong var_type'
D_4 = D_3.copy()
D_4.pop('project')
TEST_MLR_ATTRS = [
    ([], 'wrong_mode', ValueError),
    ([], 'full', 0),
    ([], 'only_missing', 0),
    ([], 'only_var_type', 0),
    ([D_1, D_1], 'wrong_mode', ValueError),
    ([D_1, D_1], 'full', 0),
    ([D_1, D_1], 'only_missing', 0),
    ([D_1, D_1], 'only_var_type', 0),
    ([D_1, D_2], 'wrong_mode', ValueError),
    ([D_1, D_2], 'full', 1),
    ([D_1, D_2], 'only_missing', 1),
    ([D_1, D_2], 'only_var_type', 0),
    ([D_1, D_3], 'wrong_mode', ValueError),
    ([D_1, D_3], 'full', 1),
    ([D_1, D_3], 'only_missing', 0),
    ([D_1, D_3], 'only_var_type', 1),
    ([D_1, D_4], 'wrong_mode', ValueError),
    ([D_1, D_4], 'full', 2),
    ([D_1, D_4], 'only_missing', 1),
    ([D_1, D_4], 'only_var_type', 1),
    ([D_1, D_2, D_3, D_4], 'wrong_mode', ValueError),
    ([D_1, D_2, D_3, D_4], 'full', 4),
    ([D_1, D_2, D_3, D_4], 'only_missing', 2),
    ([D_1, D_2, D_3, D_4], 'only_var_type', 2),
]


@pytest.mark.parametrize('datasets,mode,output', TEST_MLR_ATTRS)
@mock.patch('esmvaltool.diag_scripts.mlr.logger', autospec=True)
def test_datasets_have_mlr_attributes(mock_logger, datasets, mode, output):
    """Test checker of dataset attributes."""
    for log_level in ('debug', 'info', 'warning', 'error'):
        if isinstance(output, type):
            with pytest.raises(output):
                mlr.datasets_have_mlr_attributes(datasets, log_level=log_level,
                                                 mode=mode)
            return
        out = mlr.datasets_have_mlr_attributes(datasets, log_level=log_level,
                                               mode=mode)
        if output == 0:
            assert out is True
        else:
            assert out is False
            assert getattr(mock_logger, log_level).call_count == output


KWARGS_1 = {'dataset': 'c'}
KWARGS_2 = {'dataset': 'c', 'short_name': 'xx'}
KWARGS_3 = {'project': None}
KWARGS_4 = {'project': None, 'var_type': 'wrong var_type'}
TEST_GET_DATASETS = [
    ([D_1, D_1], {}, [D_1, D_1]),
    ([D_1, D_1], KWARGS_1, [D_1, D_1]),
    ([D_1, D_1], KWARGS_2, []),
    ([D_1, D_1], KWARGS_3, []),
    ([D_1, D_1], KWARGS_4, []),
    ([D_1, D_2], {}, [D_1, D_2]),
    ([D_1, D_2], KWARGS_1, [D_1, D_2]),
    ([D_1, D_2], KWARGS_2, [D_2]),
    ([D_1, D_2], KWARGS_3, [D_2]),
    ([D_1, D_2], KWARGS_4, []),
    ([D_3, D_4], {}, [D_3, D_4]),
    ([D_3, D_4], KWARGS_1, [D_3, D_4]),
    ([D_3, D_4], KWARGS_2, []),
    ([D_3, D_4], KWARGS_3, [D_4]),
    ([D_3, D_4], KWARGS_4, [D_4]),
    ([D_1, D_2, D_3, D_4], {}, [D_1, D_2, D_3, D_4]),
    ([D_1, D_2, D_3, D_4], KWARGS_1, [D_1, D_2, D_3, D_4]),
    ([D_1, D_2, D_3, D_4], KWARGS_2, [D_2]),
    ([D_1, D_2, D_3, D_4], KWARGS_3, [D_2, D_4]),
    ([D_1, D_2, D_3, D_4], KWARGS_4, [D_4]),
]


@pytest.mark.parametrize('input_data,kwargs,output', TEST_GET_DATASETS)
def test_get_datasets(input_data, kwargs, output):
    """Test dataset retrieving according to ``**kwargs``."""
    datasets = mlr._get_datasets(input_data, **kwargs)
    assert datasets == output


CFG_0 = {'input_data': {}}
CFG_1 = {'input_data': {'1': D_1, '2': D_1}}
CFG_2 = {'input_data': {'1': D_1, '2': D_2}}
CFG_3 = {'input_data': {'1': D_1, '3': D_3}}
CFG_4 = {'input_data': {'1': D_1, '2': D_2, '3': D_3}}
IGNORE = [
    {'dataset': 'c', 'short_name': 'd', 'var_type': 'label'},
    {'project': None},
]
TEST_GET_INPUT_DATA = [
    (CFG_0, [], True, None, ValueError, 0),
    (CFG_0, [], True, IGNORE, ValueError, 0),
    (CFG_0, [], False, None, ValueError, 0),
    (CFG_0, [], False, IGNORE, ValueError, 0),
    (CFG_0, [D_1], True, None, [D_1], 0),
    (CFG_0, [D_1], True, IGNORE, [], 0),
    (CFG_0, [D_1], False, None, [D_1], 0),
    (CFG_0, [D_1], False, IGNORE, [], 0),
    (CFG_1, [], True, None, [D_1, D_1], 0),
    (CFG_1, [], True, IGNORE, [], 0),
    (CFG_1, [], False, None, [D_1, D_1], 0),
    (CFG_1, [], False, IGNORE, [], 0),
    (CFG_1, [D_1], True, None, [D_1, D_1, D_1], 0),
    (CFG_1, [D_1], True, IGNORE, [], 0),
    (CFG_1, [D_1], False, None, [D_1, D_1, D_1], 0),
    (CFG_1, [D_1], False, IGNORE, [], 0),
    (CFG_2, [], True, None, ValueError, 1),
    (CFG_2, [], True, IGNORE, ValueError, 1),
    (CFG_2, [], False, None, [D_1, D_2], 0),
    (CFG_2, [], False, IGNORE, [], 0),
    (CFG_2, [D_1], True, None, ValueError, 1),
    (CFG_2, [D_1], True, IGNORE, ValueError, 1),
    (CFG_2, [D_1], False, None, [D_1, D_2, D_1], 0),
    (CFG_2, [D_1], False, IGNORE, [], 0),
    (CFG_3, [], True, None, ValueError, 1),
    (CFG_3, [], True, IGNORE, ValueError, 1),
    (CFG_3, [], False, None, [D_1, D_3], 0),
    (CFG_3, [], False, IGNORE, [D_3], 0),
    (CFG_3, [D_1], True, None, ValueError, 1),
    (CFG_3, [D_1], True, IGNORE, ValueError, 1),
    (CFG_3, [D_1], False, None, [D_1, D_3, D_1], 0),
    (CFG_3, [D_1], False, IGNORE, [D_3], 0),
    (CFG_4, [], True, None, ValueError, 2),
    (CFG_4, [], True, IGNORE, ValueError, 2),
    (CFG_4, [], False, None, [D_1, D_2, D_3], 0),
    (CFG_4, [], False, IGNORE, [D_3], 0),
    (CFG_4, [D_1], True, None, ValueError, 2),
    (CFG_4, [D_1], True, IGNORE, ValueError, 2),
    (CFG_4, [D_1], False, None, [D_1, D_2, D_3, D_1], 0),
    (CFG_4, [D_1], False, IGNORE, [D_3], 0),
]


@pytest.mark.parametrize(
    'cfg,ancestors,check_mlr_attrs,ignore,output,n_logger',
    TEST_GET_INPUT_DATA)
@mock.patch('esmvaltool.diag_scripts.mlr.io.netcdf_to_metadata', autospec=True)
@mock.patch('esmvaltool.diag_scripts.mlr.logger', autospec=True)
def test_get_input_data(mock_logger, mock_netcdf_to_metadata, cfg, ancestors,
                        check_mlr_attrs, ignore, output, n_logger):
    """Test retrieving of input data."""
    mock_netcdf_to_metadata.return_value = ancestors
    if isinstance(output, type):
        with pytest.raises(output):
            mlr.get_input_data(cfg,
                               check_mlr_attributes=check_mlr_attrs,
                               ignore=ignore)
        assert mock_logger.error.call_count == n_logger
        return
    input_data = mlr.get_input_data(cfg,
                                    check_mlr_attributes=check_mlr_attrs,
                                    ignore=ignore)
    assert input_data == output
    if ignore is not None:
        mock_logger.info.assert_called_once()
    else:
        mock_logger.info.assert_not_called()
