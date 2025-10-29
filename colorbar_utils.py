# -*- coding: utf-8 -*-
"""
色带工具（显式指定中文/英文字体，避免中文变方块）
"""

from __future__ import annotations
from .fonts import fontprops_pair

def add_colorbar_single(fig, ax, im, loc="right", size="1.6%", pad=0.02,
                        label="色带", label_size=11, tick_size=10,
                        label_fp=None, tick_fp=None):
    from mpl_toolkits.axes_grid1 import make_axes_locatable
    fp_en, fp_zh = fontprops_pair()
    if label_fp is None: label_fp = fp_zh
    if tick_fp  is None: tick_fp  = fp_en

    divider = make_axes_locatable(ax)
    cax = divider.append_axes(loc, size=size, pad=pad)
    orient = 'vertical' if loc in ("right", "left") else 'horizontal'
    cbar = fig.colorbar(im, cax=cax, orientation=orient)

    cbar.set_label(label, fontsize=label_size, fontproperties=label_fp)
    cbar.ax.tick_params(labelsize=tick_size)
    for t in list(cbar.ax.get_xticklabels()) + list(cbar.ax.get_yticklabels()):
        t.set_fontproperties(tick_fp)
    return cbar


def add_colorbar_grid(fig, last_im, nrows, ncols, loc="bottom", cbar_frac=0.10,
                      label_text=None, label_size=11, tick_size=10,
                      label_fp=None, tick_fp=None):
    import numpy as np
    fp_en, fp_zh = fontprops_pair()
    if label_fp is None: label_fp = fp_zh
    if tick_fp  is None: tick_fp  = fp_en

    fig.clf()
    if loc in ("bottom","top"):
        hr = [1]*nrows + [cbar_frac] if loc=="bottom" else [cbar_frac]+[1]*nrows
        gs = fig.add_gridspec(nrows=nrows+1, ncols=ncols, height_ratios=hr)
        axes = [fig.add_subplot(gs[(r+1 if loc=="top" else r), c])
                for r in range(nrows) for c in range(ncols)]
        cax  = fig.add_subplot(gs[0,:] if loc=="top" else gs[-1,:])
        cbar = fig.colorbar(last_im, cax=cax, orientation='horizontal')
    else:
        wr = [cbar_frac]+[1]*ncols if loc=="left" else [1]*ncols+[cbar_frac]
        gs = fig.add_gridspec(nrows=nrows, ncols=ncols+1, width_ratios=wr)
        axes = [fig.add_subplot(gs[r,(c+1 if loc=="left" else c)])
                for r in range(nrows) for c in range(ncols)]
        cax  = fig.add_subplot(gs[:,0] if loc=="left" else gs[:,-1])
        cbar = fig.colorbar(last_im, cax=cax, orientation='vertical')

    if label_text is not None:
        cbar.set_label(label_text, fontsize=label_size, fontproperties=label_fp)
    cbar.ax.tick_params(labelsize=tick_size)
    for t in list(cbar.ax.get_xticklabels()) + list(cbar.ax.get_yticklabels()):
        t.set_fontproperties(tick_fp)
    return fig, np.array(axes).reshape(nrows,ncols), cax, cbar
