import os
import csv
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.cm as cmx
import matplotlib.colors as colors
import matplotlib.gridspec as gridspec

import bmtk.simulator.utils.config as config

from mpl_toolkits.axes_grid1 import make_axes_locatable

def _create_node_table(node_file, node_type_file, group_key=None, exclude=[]):
    """Creates a merged nodes.csv and node_types.csv dataframe with excluded items removed. Returns a dataframe."""
    node_types_df = pd.read_csv(node_type_file, sep=' ', index_col='node_type_id')
    nodes_df = pd.read_csv(node_file, sep=' ', index_col='node_id')
    full_df = pd.merge(left=nodes_df, right=node_types_df, how='left', left_on='node_type_id', right_index=True)

    if group_key is not None and len(exclude) > 0:
        # Make sure sure we group-key exists as column
        if group_key not in full_df:
            raise Exception('Could not find column {}'.format(group_key))

        group_keys = set(nodes_df[group_key].unique()) - set(exclude)
        groupings = nodes_df.groupby(group_key)
        # remove any rows with matching column value
        for cond in exclude:
            full_df = full_df[full_df[group_key] != cond]

    return full_df

def _count_spikes(spikes_file, max_gid, interval=None):
    def parse_line(line):
        ts, gid = line.strip().split(' ')
        return float(ts), int(gid)

    if interval is None:
        t_max = t_bounds_low = -1.0
        t_min = t_bounds_high = 1e16
    elif  hasattr(interval, "__getitem__") and len(interval) == 2:
        t_min = t_bounds_low = interval[0]
        t_max = t_bounds_high = interval[1]
    elif isinstance(interval, float):
        t_max = t_min = t_bounds_low = interval[0]
        t_bounds_high = 1e16
    else:
        raise Exception("Unable to determine interval.")

    spikes = [[] for _ in xrange(max_gid+1)]
    spike_sums = np.zeros(max_gid+1)
    with open(spikes_file, 'r') as fspikes:
        for line in fspikes:
            ts, gid = parse_line(line)
            if gid <= max_gid and t_bounds_low <= ts <= t_bounds_high:
                spikes[gid].append(ts)
                spike_sums[gid] += 1
                t_min = ts if ts < t_min else t_min
                t_max = ts if ts > t_max else t_max

    return spikes, spike_sums/(float(t_max-t_min)*1e-3)



def plot_spikes_config(configure, group_key=None, exclude=[], save_as=None, show_plot=True):
    if isinstance(configure, basestring):
        conf = config.from_json(configure)
    elif isinstance(configure, dict):
        conf = configure
    else:
        raise Exception("configure variable must be either a json dictionary or json file name.")

    cells_file_name = conf['internal']['nodes']
    cell_models_file_name = conf['internal']['node_types']
    spikes_file = conf['output']['spikes_ascii']

    plot_spikes(cells_file_name, cell_models_file_name, spikes_file, group_key, exclude, save_as, show_plot)



def plot_spikes(cells_file, cell_models_file, spikes_file, group_key=None, exclude=[], save_as=None, show=True,
                title=None):
    # check if can be shown and/or saved
    #if save_as is not None:
    #    if os.path.exists(save_as):
    #        raise Exception('file {} already exists. Cannot save.'.format(save_as))

    cm_df = pd.read_csv(cell_models_file, sep=' ')
    cm_df.set_index('node_type_id', inplace=True)

    c_df = pd.read_csv(cells_file, sep=' ')
    c_df.set_index('node_id', inplace=True)
    nodes_df = pd.merge(left=c_df,
                        right=cm_df,
                        how='left',
                        left_on='node_type_id',
                        right_index=True)  # use 'model_id' key to merge, for right table the "model_id" is an index


    spike_times, spike_gids = np.loadtxt(spikes_file, dtype='float32,int', unpack=True)
    # spike_gids, spike_times = np.loadtxt(spikes_file, dtype='int,float32', unpack=True)

    spike_times = spike_times * 1.0e-3

    if group_key is not None:
        if group_key not in nodes_df:
            raise Exception('Could not find column {}'.format(group_key))
        groupings = nodes_df.groupby(group_key)

        n_colors = nodes_df[group_key].nunique()
        color_norm = colors.Normalize(vmin=0, vmax=(n_colors-1))
        scalar_map = cmx.ScalarMappable(norm=color_norm, cmap='hsv')
        color_map = [scalar_map.to_rgba(i) for i in range(0, n_colors)]
    else:
        groupings = [(None, nodes_df)]
        color_map = ['blue']

    #marker = '.' if len(nodes_df) > 1000 else 'o'
    marker = 'o'

    # Create plot
    gs = gridspec.GridSpec(2, 1, height_ratios=[7, 1])
    ax1 = plt.subplot(gs[0])
    gid_min = 10**10
    gid_max = -1
    for color, (group_name, group_df) in zip(color_map, groupings):
        if group_name in exclude:
            continue
        group_min_gid = min(group_df.index.tolist())
        group_max_gid = max(group_df.index.tolist())
        gid_min = group_min_gid if group_min_gid <= gid_min else gid_min
        gid_max = group_max_gid if group_max_gid > gid_max else gid_max

        gids_group = group_df.index
        indexes = np.in1d(spike_gids, gids_group)
        ax1.scatter(spike_times[indexes], spike_gids[indexes], marker=marker, facecolors=color, label=group_name, lw=0, s=5)

    #ax1.set_xlabel('time (s)')
    ax1.axes.get_xaxis().set_visible(False)
    ax1.set_ylabel('cell_id')
    ax1.set_xlim([0, max(spike_times)])
    ax1.set_ylim([gid_min, gid_max])
    plt.legend(markerscale=2, scatterpoints=1)

    ax2 = plt.subplot(gs[1])
    plt.hist(spike_times, 100)
    ax2.set_xlabel('time (s)')
    ax2.axes.get_yaxis().set_visible(False)
    if title is not None:
        ax1.set_title(title)

    if save_as is not None:
        plt.savefig(save_as)

    if show:
        plt.show()


def plot_ratess(cells_file, cell_models_file, spikes_file, group_key='pop_name', exclude=['LIF_inh', 'LIF_exc'], save_as=None, show_plot=True):
    #if save_as is not None:
    #    if os.path.exists(save_as):
    #        raise Exception('file {} already exists. Cannot save.'.format(save_as))

    cm_df = pd.read_csv(cell_models_file, sep=' ')
    cm_df.set_index('node_type_id', inplace=True)

    c_df = pd.read_csv(cells_file, sep=' ')
    c_df.set_index('node_id', inplace=True)
    nodes_df = pd.merge(left=c_df,
                        right=cm_df,
                        how='left',
                        left_on='node_type_id',
                        right_index=True)  # use 'model_id' key to merge, for right table the "model_id" is an index

    for cond in exclude:
        nodes_df = nodes_df[nodes_df[group_key] != cond]

    groupings = nodes_df.groupby(group_key)
    n_colors = nodes_df[group_key].nunique()
    color_norm = colors.Normalize(vmin=0, vmax=(n_colors - 1))
    scalar_map = cmx.ScalarMappable(norm=color_norm, cmap='hsv')
    color_map = [scalar_map.to_rgba(i) for i in range(0, n_colors)]


    spike_times, spike_gids = np.loadtxt(spikes_file, dtype='float32,int', unpack=True)
    rates = np.zeros(max(spike_gids) + 1)
    for ts, gid in zip(spike_times, spike_gids):
        if ts < 500.0:
            continue
        rates[gid] += 1

    for color, (group_name, group_df) in zip(color_map, groupings):
        print group_name
        print group_df.index
        print rates[group_df.index]
        plt.plot(group_df.index, rates[group_df.index], '.', color=color)

    plt.show()

    print n_colors
    exit()



    group_keys = set(nodes_df[group_key].unique()) - set(exclude)
    groupings = nodes_df.groupby(group_key)

    n_colors = len(group_keys)
    color_norm = colors.Normalize(vmin=0, vmax=(n_colors - 1))
    scalar_map = cmx.ScalarMappable(norm=color_norm, cmap='hsv')
    color_map = [scalar_map.to_rgba(i) for i in range(0, n_colors)]

    for color, (group_name, group_df) in zip(color_map, groupings):
        print group_name
        print group_df.index

    exit()


    """
    print color_map
    exit()

    n_colors = nodes_df[group_key].nunique()
    color_norm = colors.Normalize(vmin=0, vmax=(n_colors - 1))
    scalar_map = cmx.ScalarMappable(norm=color_norm, cmap='hsv')
    color_map = [scalar_map.to_rgba(i) for i in range(0, n_colors)]
    """

    spike_times, spike_gids = np.loadtxt(spikes_file, dtype='float32,int', unpack=True)
    rates = np.zeros(max(spike_gids)+1)

    for ts, gid in zip(spike_times, spike_gids):
        if ts < 500.0:
            continue

        rates[gid] += 1

    rates = rates / 3.0

    plt.plot(xrange(max(spike_gids)+1), rates, '.')
    plt.show()


def plot_rates(cells_file, cell_models_file, spikes_file, group_key=None, exclude=[], interval=None, show=True,
               title=None, save_as=None, smoothed=False):
    def smooth(data, window=100):
        h = int(window/2)
        x_max = len(data)
        return [np.mean(data[max(0, x-h):min(x_max, x+h)]) for x in xrange(0, x_max)]

    nodes_df = _create_node_table(cells_file, cell_models_file, group_key, exclude)
    _, spike_rates = _count_spikes(spikes_file, max(nodes_df.index), interval)

    if group_key is not None:
        groupings = nodes_df.groupby(group_key)
        group_order = {k: i for i, k in enumerate(nodes_df[group_key].unique())}

        n_colors = len(group_order)
        color_norm = colors.Normalize(vmin=0, vmax=(n_colors-1))
        scalar_map = cmx.ScalarMappable(norm=color_norm, cmap='hsv')
        color_map = [scalar_map.to_rgba(i) for i in range(0, n_colors)]
        ordered_groupings = [(group_order[name], c, name, df) for c, (name, df) in zip(color_map, groupings)]

    else:
        ordered_groupings = [(0, 'blue', None, nodes_df)]

    keys = ['' for _ in xrange(len(group_order))]
    means = [0 for _ in xrange(len(group_order))]
    stds = [0 for _ in xrange(len(group_order))]
    fig = plt.figure()
    ax1 = fig.add_subplot(111)
    for indx, color, group_name, group_df in ordered_groupings:
        keys[indx] = group_name
        means[indx] = np.mean(spike_rates[group_df.index])
        stds[indx] = np.std(spike_rates[group_df.index])
        y = smooth(spike_rates[group_df.index]) if smoothed else spike_rates[group_df.index]
        ax1.plot(group_df.index, y, '.', color=color, label=group_name)

    max_rate = np.max(spike_rates)
    ax1.set_ylim(0, 50)#max_rate*1.3)
    ax1.set_ylabel('Hz')
    ax1.set_xlabel('gid')
    ax1.legend(fontsize='x-small')
    if title is not None:
        ax1.set_title(title)
    if save_as is not None:
        plt.savefig(save_as)

    plt.figure()
    plt.errorbar(xrange(len(means)), means, stds, linestyle='None', marker='o')
    plt.xlim(-0.5, len(color_map)-0.5) # len(color_map) == last_index + 1
    plt.ylim(0, 50.0)# max_rate*1.3)
    plt.xticks(xrange(len(means)), keys)
    if title is not None:
        plt.title(title)
    if save_as is not None:
        if save_as.endswith('.jpg'):
            base = save_as[0:-4]
        elif save_as.endswith('.jpeg'):
            base = save_as[0:-5]
        else:
            base = save_as

        plt.savefig('{}.summary.jpg'.format(base))
        with open('{}.summary.csv'.format(base), 'w') as f:
            f.write('population mean stddev\n')
            for i, key in enumerate(keys):
                f.write('{} {} {}\n'.format(key, means[i], stds[i]))

    if show:
        plt.show()

def plot_rates_popnet(cell_models_file, rates_file, model_keys=None, save_as=None, show_plot=True):
    """Initial method for plotting popnet output

    :param cell_models_file:
    :param rates_file:
    :param model_keys:
    :param save_as:
    :param show_plot:
    :return:
    """

    pops_df = pd.read_csv(cell_models_file, sep=' ')
    lookup_col = model_keys if model_keys is not None else 'node_type_id'
    pop_keys = {str(r['node_type_id']): r[lookup_col] for _, r in pops_df.iterrows()}

    # organize the rates file by population
    rates = {pop_name: ([], []) for pop_name in pop_keys.keys()}
    with open(rates_file, 'r') as f:
        reader = csv.reader(f, delimiter=' ')
        for row in reader:
            if row[0] in rates:
                rates[row[0]][0].append(row[1])
                rates[row[0]][1].append(row[2])

    # plot the rates
    plt.figure()
    for pop_name, r in rates.iteritems():
        label = pop_keys[pop_name]
        times = r[0]
        rates = r[1]
        if len(times) == 0:
            continue

        plt.plot(times, rates, label=label)

    plt.legend(fontsize='x-small')
    plt.xlabel('time (s)')
    plt.ylabel('firing rates (Hz)')

    if save_as is not None:
        plt.savefig(save_as)

    if show_plot:
        plt.show()

def plot_avg_rates(cell_models_file, rates_file, model_keys=None, save_as=None, show_plot=True):
    pops_df = pd.read_csv(cell_models_file, sep=' ')
    lookup_col = model_keys if model_keys is not None else 'node_type_id'
    pop_keys = {str(r['node_type_id']): r[lookup_col] for _, r in pops_df.iterrows()}

    # organize the rates file by population
    rates = {pop_name: [] for pop_name in pop_keys.keys()}
    with open(rates_file, 'r') as f:
        reader = csv.reader(f, delimiter=' ')
        for row in reader:
            if row[0] in rates:
                #rates[row[0]][0].append(row[1])
                rates[row[0]].append(float(row[2]))

    labels = []
    means = []
    stds = []
    #print rates
    for pop_name in pops_df['node_type_id'].unique():
        r = rates[str(pop_name)]
        if len(r) == 0:
            continue

        labels.append(pop_keys.get(str(pop_name), str(pop_name)))
        means.append(np.mean(r))
        stds.append(np.std(r))

    plt.figure()
    plt.errorbar(xrange(len(means)), means, stds, linestyle='None', marker='o')
    plt.xlim(-0.5, len(means) - 0.5)
    plt.xticks(xrange(len(means)), labels)
    plt.ylabel('firing rates (Hz)')

    if save_as is not None:
        plt.savefig(save_as)

    if show_plot:
        plt.show()


def plot_tuning(sg_analysis, node, band, Freq=0, show=True, save_as=None):
    def index_for_node(node, band):
        if node == 's4':
            mask = sg_analysis.node_table.node == node
        else:
            mask = (sg_analysis.node_table.node == node) & (sg_analysis.node_table.band == band)
        return str(sg_analysis.node_table[mask].index[0])
    
    index = index_for_node(node, band)

    key = index + '/sg/tuning'
    analysis_file = sg_analysis.get_tunings_file()

    tuning_matrix = analysis_file[key].value[:, :, :, Freq]

    n_or, n_sf, n_ph = tuning_matrix.shape

    vmax = np.max(tuning_matrix[:, :, :])
    vmin = np.min(tuning_matrix[:, :, :])

    #fig, ax = plt.subplots(1, n_ph, figsize=(12, 16), sharex=True, sharey=True)
    fig, ax = plt.subplots(1, n_ph, figsize=(13.9, 4.3), sharex=False, sharey=True)

    print sg_analysis.orientations
    for phase in range(n_ph):
        tuning_to_plot = tuning_matrix[:, :, phase]

        im = ax[phase].imshow(tuning_to_plot, interpolation='nearest', vmax=vmax, vmin=vmin)
        ax[phase].set_xticklabels([0] + list(sg_analysis.spatial_frequencies))
        ax[phase].set_yticklabels([0] + list(sg_analysis.orientations))

        ax[phase].set_title('phase = {}'.format(sg_analysis.phases[phase]))
        ax[phase].set_xlabel('spatial_frequency')
        if phase == 0:
            ax[phase].set_ylabel('orientation')

    fig.subplots_adjust(right=0.90)
    cbar_ax = fig.add_axes([0.92, 0.10, 0.02, 0.75])
    cbar = fig.colorbar(im, cax=cbar_ax, ticks=[vmin, 0.0, vmax])

    if save_as is not None:
        plt.savefig(save_as)

    if show:
        plt.show()


            #config_file =
#plot_spikes('../../examples/pointnet/example2/config.json', 'pop_name')