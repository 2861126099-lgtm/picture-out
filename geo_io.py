# -*- coding: utf-8 -*-
import os, glob
import numpy as np
import rasterio
from rasterio.warp import calculate_default_transform, reproject, Resampling
from rasterio.features import geometry_mask
from rasterio.transform import array_bounds
import geopandas as gpd
from .config import DST_CRS

def resolve_path(path_pattern: str) -> str:
    if any(ch in path_pattern for ch in "*?"):
        matches = sorted(glob.glob(path_pattern))
        if not matches:
            raise FileNotFoundError(f"未找到匹配：{path_pattern}")
        return os.path.abspath(matches[0])
    if not os.path.exists(path_pattern):
        raise FileNotFoundError(f"文件不存在：{path_pattern}")
    return os.path.abspath(path_pattern)

def _read_gdf_any(path):
    try:
        return gpd.read_file(path)
    except Exception:
        return gpd.read_file(path, engine="fiona")

def read_border_gdf(border_shp: str) -> gpd.GeoDataFrame:
    if not border_shp or not os.path.exists(border_shp):
        raise FileNotFoundError("边界SHP路径为空或文件不存在。")
    gdf = _read_gdf_any(border_shp)
    if gdf.crs is None:
        raise ValueError("边界SHP缺少CRS。")
    return gdf

def read_project_clip(raster_path, border_gdf, dst_crs, year_start, year_end, as_yearly):
    span = max(1, int(year_end) - int(year_start) + 1)
    with rasterio.open(raster_path) as src:
        a = src.read(1).astype("float32")
        if src.nodata is not None:
            a = np.where(a == src.nodata, np.nan, a)
        tfm, w, h = calculate_default_transform(src.crs, dst_crs, src.width, src.height, *src.bounds)
        arr = np.full((h, w), np.nan, dtype="float32")
        reproject(source=a, destination=arr,
                  src_transform=src.transform, src_crs=src.crs,
                  dst_transform=tfm, dst_crs=dst_crs,
                  src_nodata=np.nan, dst_nodata=np.nan,
                  resampling=Resampling.bilinear)
    g = border_gdf.to_crs(dst_crs) if border_gdf.crs != dst_crs else border_gdf
    mask = geometry_mask([geom for geom in g.geometry if geom is not None],
                         out_shape=arr.shape, transform=tfm, invert=True)
    arr = np.where(mask, arr, np.nan)
    if as_yearly:
        arr = arr / float(span)
    return arr, tfm

def extent_from_transform(arr, tfm):
    left, bottom, right, top = array_bounds(arr.shape[0], arr.shape[1], tfm)
    return [left, right, bottom, top]

def nice_length_km(width_m):
    target = (width_m / 4.8) / 1000.0
    mag = 10 ** np.floor(np.log10(target)) if target > 0 else 1
    for k in [1, 2, 5, 10]:
        cand = k * mag
        if cand >= target:
            return int(cand)
    return max(1, int(round(target)))
