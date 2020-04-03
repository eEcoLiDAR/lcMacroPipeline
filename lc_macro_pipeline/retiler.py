import os
import pdal
import pylas
import json

from lc_macro_pipeline.grid import Grid
from lc_macro_pipeline.pipeline_remote_data import PipelineRemoteData
from lc_macro_pipeline.utils import check_file_exists, check_dir_exists


class Retiler(PipelineRemoteData):
    """ Split point cloud data into smaller tiles on a regular grid. """

    def __init__(self):
        self.pipeline = ('tiling', 'split_and_redistribute', 'validate')
        self.temp_folder = None
        self.filename = None
        self.tiled_temp_folder = None
        self.grid = Grid()

    def tiling(self, min_x, min_y, max_x, max_y, n_tiles_side):
        """
        Setup the grid to which the input file is retiled.

        :param min_x: min x value of tiling schema
        :param min_y: max y value of tiling schema
        :param max_x: min x value of tiling schema
        :param max_y: max y value of tiling schema
        :param n_tiles_side: number of tiles along axis. Tiling MUST be square
        (enforced)
        """
        self.grid.setup(min_x, min_y, max_x, max_y, n_tiles_side)
        return self

    def split_and_redistribute(self):
        """
        Split the input file using PDAL and organize the tiles in subfolders
        using the location on the input grid as naming scheme.
        """
        check_file_exists(self.input_file, should_exist=True)
        _run_PDAL_splitter(self.input_file, self.output_folder,
                           self.grid.grid_mins, self.grid.grid_maxs,
                           self.grid.n_tiles_side)
        tiles = [f for f in self.output_folder.iterdir()
                 if (f.is_file()
                     and f.suffix.lower() == self.input_file.suffix.lower()
                     and f.stem.startswith(self.input_file.stem)
                     and f.name != self.input_file.name)]
        for tile in tiles:
            (_, tile_mins, tile_maxs, _, _) = _get_details_pc_file(str(tile))

            # Get central point to identify associated tile
            cpX = tile_mins[0] + ((tile_maxs[0] - tile_mins[0]) / 2.)
            cpY = tile_mins[1] + ((tile_maxs[1] - tile_mins[1]) / 2.)
            tile_id = _get_tile_name(*self.grid.get_tile_index(cpX, cpY))

            retiled_folder = self.output_folder.joinpath(tile_id)
            check_dir_exists(retiled_folder, should_exist=True, mkdir=True)
            tile.rename(retiled_folder.joinpath(tile.name))
        return self

    def validate(self, write_record_to_file=True):
        """
        Validate the produced output by checking consistency in the number
        of input and output points.
        """
        check_file_exists(self.input_file, should_exist=True)
        (parent_points, _, _, _, _) = _get_details_pc_file(self.input_file.as_posix())
        valid_split = False
        split_points = 0
        redistributed_to = []
        tiles = self.output_folder.glob('tile_*/{}*'.format(self.input_file.stem))

        for tile in tiles:
            if tile.is_file():
                (tile_points, _, _, _, _) = _get_details_pc_file(tile.as_posix())
                split_points += tile_points
                redistributed_to.append(tile.parent.name)

        if parent_points == split_points:
            valid_split = True

        retile_record = {'file': self.input_file.as_posix(),
                         'redistributed_to': redistributed_to,
                         'validated': valid_split}

        if write_record_to_file:
            _write_record(self.input_file.stem,
                          self.output_folder,
                          retile_record)
        return self


def _get_details_pc_file(filename):
    try:
        with pylas.open(filename) as file:
            count = file.header.point_count
            mins = file.header.mins
            maxs = file.header.maxs
            scales = file.header.scales
            offsets = file.header.offsets
        return (count, mins, maxs, scales, offsets)

    except IOError:
        print('failure to open {}'.format(filename))
        return None


def _get_tile_name(x_index, y_index):
    return 'tile_{}_{}'.format(int(x_index), int(y_index))


def _run_PDAL_splitter(filename, tiled_temp_folder, tiling_mins, tiling_maxs,
                       n_tiles_side):
    length_PDAL_tile = ((tiling_maxs[0] - tiling_mins[0]) /
                        float(n_tiles_side))

    outfile_with_placeholder = "_#".join([filename.stem, filename.suffix])
    outfilepath = tiled_temp_folder.joinpath(outfile_with_placeholder)

    PDAL_pipeline_dict = {
        "pipeline": [
            filename.as_posix(),
            {
                "type": "filters.splitter",
                "origin_x": "{}".format(tiling_mins[0]),
                "origin_y": "{}".format(tiling_mins[1]),
                "length": "{}".format(length_PDAL_tile)
            },
            {
                "type": "writers.las",
                "filename": outfilepath.as_posix(),
                "forward": ["scale_x", "scale_y", "scale_z"],
                "offset_x": "auto",
                "offset_y": "auto",
                "offset_z": "auto"
            }
        ]
    }
    PDAL_pipeline = pdal.Pipeline(json.dumps(PDAL_pipeline_dict))
    PDAL_pipeline.execute()


def _write_record(input_tile, temp_folder, retile_record):
    record_file = os.path.join(temp_folder, os.path.splitext(
        input_tile)[0] + '_retile_record.js')

    with open(record_file, 'w') as recfile:
        recfile.write(json.dumps(retile_record, indent=4, sort_keys=True))
