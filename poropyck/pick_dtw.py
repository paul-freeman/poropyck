"""Dynamic time warping"""
import argparse
import json

import matplotlib.pyplot as plt
import mcerp3 as mc
import numpy as np
from mpl_toolkits.mplot3d import Axes3D  # pylint: disable=unused-import
from pkg_resources import Requirement, resource_filename
from scipy.signal import hilbert
from scipy.stats import norm

from dtw import dtw  # pylint: disable=no-name-in-module

# colours
TEMPLATE_COLOR = 'tan'
QUERY_COLOR = 'blue'
HIGHLIGHT_COLOR = 'thistle'
ENVELOPE_COLOR = 'lightpink'
ENVELOPE_ALPHA = 0.4
PATH_COLOR = 'black'


class Poropyck:
    """compare using dynamic time warping"""

    def __init__(self, template, query, length):
        self.fig = plt.figure()
        self.ax = {
            'template': self.fig.add_axes([0.030, 0.865, 0.90, 0.100]),
            'query': self.fig.add_axes([0.030, 0.700, 0.90, 0.100]),
            'dtw': self.fig.add_axes([0, 0.15, 0.200*1.65, 0.220*1.65], projection='3d'),
            'summary': self.fig.add_axes([0.100+0.32, 0.08, 0.25, 0.4]),

            'template_clicks': self.fig.add_axes([0.400+0.32, 0.38, 0.1, 0.200]),
            'template_velocity': self.fig.add_axes([0.520+0.32, 0.38, 0.1, 0.200]),
            # 'template_bulk': self.fig.add_axes([0.640, 0.355, 0.1, 0.200]),
            # 'template_poisson': self.fig.add_axes([0.760, 0.355, 0.1, 0.200]),
            # 'template_youngs': self.fig.add_axes([0.880, 0.355, 0.1, 0.200]),

            'query_clicks': self.fig.add_axes([0.400+0.32, 0.080, 0.1, 0.200]),
            'query_velocity': self.fig.add_axes([0.520+0.32, 0.080, 0.1, 0.200]),
            # 'query_bulk': self.fig.add_axes([0.640, 0.080, 0.1, 0.200]),
            # 'query_poisson': self.fig.add_axes([0.760, 0.080, 0.1, 0.200]),
            # 'query_youngs': self.fig.add_axes([0.880, 0.080, 0.1, 0.200])
        }
        self.ax['x'] = self.fig.add_axes(
            [0.100+0.32, 0.48, 0.25, 0.1],
            sharex=self.ax['summary']
        )
        self.ax['y'] = self.fig.add_axes(
            [0.030+0.32, 0.08, 0.07, 0.4],
            sharey=self.ax['summary']
        )

        self.ax['template'].get_yaxis().set_visible(False)
        self.ax['query'].get_yaxis().set_visible(False)
        self.ax['x'].get_yaxis().set_visible(False)
        self.ax['y'].get_xaxis().set_visible(False)
        self.ax['template_clicks'].get_yaxis().set_visible(False)
        self.ax['query_clicks'].get_yaxis().set_visible(False)
        self.ax['template_velocity'].get_yaxis().set_visible(False)
        self.ax['query_velocity'].get_yaxis().set_visible(False)
        self.ax['summary'].get_yaxis().tick_right()
        self.ax['x'].get_xaxis().tick_top()
        self.ax['template'].set_title(
            'Template signal: select the area of interest')
        self.ax['query'].set_title(
            'Query signal: select the area of interest')

        self.length = length

        self.template = template
        self.query = query

        self.indices1 = None
        self.indices1a = None
        self.indices1h = None
        self.indices2 = None
        self.indices2a = None
        self.indices2h = None

        self.fig.canvas.mpl_connect('button_press_event', self.onpress)
        self.fig.canvas.mpl_connect('button_release_event', self.onrelease)
        self.fig.canvas.mpl_connect('motion_notify_event', self.onmotion)
        self.fig.canvas.mpl_connect('pick_event', self.onpick)

        self.summary_xlim = self.ax['summary'].get_xlim()
        self.summary_ylim = self.ax['summary'].get_ylim()

        self.template.plot(self.ax['template'])
        self.query.plot(self.ax['query'])
        plt.show()

    def onpress(self, event):
        """mouse button pressed"""
        if event.inaxes is self.ax['template'] or event.inaxes is self.ax['query']:
            if event.inaxes is self.ax['template']:
                self.template.onpress(event)
                self.template.plot(self.ax['template'])
            if event.inaxes is self.ax['query']:
                self.query.onpress(event)
                self.query.plot(self.ax['query'])
            self.clear_output_axes()
            self.fig.canvas.draw_idle()

    def onrelease(self, event):
        """mouse button released"""
        if self.template.pressed or self.query.pressed:
            if self.template.pressed:
                self.template.onrelease(event)
                self.template.plot(self.ax['template'])
            if self.query.pressed:
                self.query.onrelease(event)
                self.query.plot(self.ax['query'])
            self.run_dtw()
            self.fig.canvas.draw_idle()

    def onmotion(self, event):
        """mouse moves"""
        if event.inaxes is self.ax['template'] or event.inaxes is self.ax['query']:
            if self.template.pressed or self.query.pressed:
                if self.template.pressed:
                    self.template.move_line(event)
                    self.template.plot(self.ax['template'])
                if self.query.pressed:
                    self.query.move_line(event)
                    self.query.plot(self.ax['query'])
                self.fig.canvas.draw_idle()

    def onpick(self, event):
        """pick values from the active plot"""
        indices = event.ind
        xdata = event.artist.get_xdata()[indices]
        ydata = event.artist.get_ydata()[indices]
        mouse_x, mouse_y = event.mouseevent.xdata, event.mouseevent.ydata
        dists = np.sqrt((np.array(xdata)-mouse_x)**2 +
                        (np.array(ydata)-mouse_y)**2)
        xpoint = xdata[np.argmin(dists)]
        ypoint = ydata[np.argmin(dists)]

        self.template.picks.append(ypoint)
        self.query.picks.append(xpoint)
        self.plot_summary(self.ax['x'], self.ax['y'], self.ax['summary'])
        self.highlight_summary()
        self.plot_monte_carlo()
        self.fig.canvas.draw_idle()

    def onxzoom(self, axes):
        """summary axes is zoomed - x"""
        self.summary_xlim = axes.get_xlim()

    def onyzoom(self, axes):
        """summary axes is zoomed - y"""
        self.summary_ylim = axes.get_ylim()

    def run_dtw(self):
        """run dynamic time warping"""
        self.indices1, self.indices2 = dtw(
            self.query.picked_signal, self.template.picked_signal)[1:3]
        self.indices1h, self.indices2h = dtw(
            self.query.hilbert_abs(), self.template.hilbert_abs())[1:3]
        self.indices1a, self.indices2a = dtw(
            self.query.hilbert_angle(), self.template.hilbert_angle())[1:3]

        self.plot_dtw(self.ax['dtw'])
        self.plot_summary(self.ax['x'], self.ax['y'], self.ax['summary'])

    def plot_dtw(self, ax):
        """plot the 3D DTW data"""
        template_times = self.template.picked_times
        template_signal = self.template.picked_signal
        query_times = self.query.picked_times
        query_signal = self.query.picked_signal
        ax.clear()
        ax.set_title('Dynamic Time Warping Visualization', y=1.15)
        ax.plot(template_times, template_signal, zs=1, c=self.template.color)
        ax.plot(query_times, query_signal, zs=0, c=self.query.color)
        for i in np.arange(0, len(self.indices1) - 1, 20):
            x_start = np.take(template_times, self.indices2[i].astype(int) - 1)
            x_end = np.take(query_times, self.indices1[i].astype(int) - 1)
            y_start = np.take(
                template_signal, self.indices2[i].astype(int) - 1)
            y_end = np.take(query_signal, self.indices1[i].astype(int) - 1)
            ax.plot(
                [x_start, x_end], [y_start, y_end],
                '-', color=HIGHLIGHT_COLOR, lw=0.5, zs=[1, 0]
            )
        self.summary_xlim = (self.query.start, self.query.finish)
        self.summary_ylim = (self.template.start, self.template.finish)

    def plot_summary(self, x_ax, y_ax, summary_ax):
        """plot the time warping summary"""
        query_times = self.query.picked_times
        query_signal = self.query.picked_signal
        queryh = self.query.hilbert_abs()
        # querya = self.query.hilbert_angle()
        x_ax.clear()
        x_ax.set_title('Select points of interest', y=1.25)
        x_ax.plot(query_times, query_signal, '-', c=QUERY_COLOR, lw=2)
        x_ax.fill_between(query_times, queryh, -queryh,
                          color=ENVELOPE_COLOR, alpha=ENVELOPE_ALPHA)
        try:
            x_ax.set_ylim(1.1 * np.min(query_signal),
                          1.1 * np.max(queryh))
        except TypeError:
            x_ax.set_ylim(-1, 1)
        x_ax.grid(True, axis='x', color='lightgrey')
        y_ax.tick_params(axis='x', which='major')

        template_times = self.template.picked_times
        template_signal = self.template.picked_signal
        templateh = self.template.hilbert_abs()
        # templatea = self.template.hilbert_angle()
        y_ax.clear()
        y_ax.plot(template_signal, template_times, c=TEMPLATE_COLOR, lw=2)
        y_ax.fill_betweenx(template_times, templateh, -templateh,
                           color=ENVELOPE_COLOR, alpha=ENVELOPE_ALPHA)
        try:
            y_ax.set_xlim(1.1 * np.min(template_signal),
                          1.1 * np.max(templateh))
        except TypeError:
            y_ax.set_xlim(-1, 1)
        y_ax.grid(True, axis='y', color='lightgrey')
        y_ax.tick_params(axis='y', which='major')
        y_ax.invert_xaxis()

        end = len(self.indices1)
        idxto = np.take(template_times, self.indices2[:end].astype(int) - 1)
        idxqo = np.take(query_times, self.indices1.astype(int) - 1)
        # to = template_signal[self.indices2[:end] - 1]
        # qo = query_signal[self.indices1 - 1]

        end = len(self.indices1h)
        idxtoh = np.take(template_times, self.indices2h[:end].astype(int) - 1)
        idxqoh = np.take(query_times, self.indices1h.astype(int) - 1)
        # toh = templateh[self.indices2h[:end] - 1]
        # qoh = queryh[self.indices1h - 1]

        # end = len(self.indices1a)
        # idxtoa = template_times[self.indices2a[:end] - 1]
        # idxqoa = query_times[self.indices1a - 1]
        # toa = templatea[self.indices2a[:end] - 1]
        # qoa = querya[self.indices1a - 1]

        summary_ax.clear()
        summary_ax.axis('equal')
        summary_ax.fill_between(idxqoh, idxtoh, idxqoh,
                                color=ENVELOPE_COLOR, alpha=ENVELOPE_ALPHA)
        summary_ax.fill_betweenx(idxqoh, idxtoh, idxqoh,
                                 color=ENVELOPE_COLOR, alpha=ENVELOPE_ALPHA)
        summary_ax.plot(idxqo, idxto, c=TEMPLATE_COLOR, picker=5, lw=2)
        summary_ax.plot(idxqo, idxto, c=QUERY_COLOR, alpha=0.25, lw=2)

        times = np.linspace(
            0, np.max([self.template.times, self.query.times]), 10)
        summary_ax.plot(times, times, color=HIGHLIGHT_COLOR, lw=1)
        summary_ax.tick_params(axis='both', which='major')
        summary_ax.grid(color='lightgrey')
        summary_ax.set_xlim(self.summary_xlim)
        summary_ax.set_ylim(self.summary_ylim)
        summary_ax.callbacks.connect('xlim_changed', self.onxzoom)
        summary_ax.callbacks.connect('ylim_changed', self.onyzoom)

        x_ax.set_xlim(summary_ax.get_xlim())
        y_ax.set_ylim(summary_ax.get_ylim())

    def highlight_summary(self):
        """highlight summary plot after points are picked"""
        ax = self.ax['summary']
        ax_x = self.ax['x']
        ax_y = self.ax['y']

        min_, max_, mean, _ = self.query.time_picks()
        ax.axvspan(min_, max_, alpha=0.4, color=self.query.color)
        ax.axvline(mean, linewidth=2, color=self.query.color)
        ax_x.axvspan(min_, max_, alpha=0.4, color=self.query.color)
        ax_x.axvline(mean, linewidth=2, color=self.query.color)

        min_, max_, mean, _ = self.template.time_picks()
        ax.axhspan(min_, max_, alpha=0.4, color=self.template.color)
        ax.axhline(mean, linewidth=2, color=self.template.color)
        ax_y.axhspan(min_, max_, alpha=0.4, color=self.template.color)
        ax_y.axhline(mean, linewidth=2, color=self.template.color)

    def plot_monte_carlo(self):
        """plot the Monte Carlo distributions"""
        self.template.plot_clicks(self.ax['template_clicks'])
        self.template.plot_velocity(self.ax['template_velocity'])
        # self.template.plot_bulk(self.ax['template_bulk'])
        # self.template.plot_poisson(self.ax['template_poisson'])
        # self.template.plot_youngs(self.ax['template_youngs'])
        self.query.plot_clicks(self.ax['query_clicks'])
        self.query.plot_velocity(self.ax['query_velocity'])
        # self.query.plot_bulk(self.ax['query_bulk'])
        # self.query.plot_poisson(self.ax['query_poisson'])
        # self.query.plot_youngs(self.ax['query_youngs'])

    def clear_output_axes(self):
        """clear all output data"""
        self.ax['dtw'].clear()
        self.ax['summary'].clear()
        self.ax['x'].clear()
        self.ax['y'].clear()
        self.ax['template_clicks'].clear()
        self.ax['query_clicks'].clear()
        self.ax['template_velocity'].clear()
        self.ax['query_velocity'].clear()


class Signal:
    """one signal to be compared"""

    def __init__(self, data, length, density, shear, color='blue'):
        secs, self.signal = data
        self.times = secs * 1e6
        self.length = length
        self.density = density
        self.shear = shear
        self.color = color
        self.start = self.times[len(self.times) // 2]
        self.finish = self.times[len(self.times) // 2 + 1]
        self.pressed = False
        self.picks = []
        self.picked_times, self.picked_signal = self.get_picked_data()

    def onpress(self, event):
        """mouse button pressed"""
        self.pressed = True
        self.picks = []
        self.move_line(event)

    def onrelease(self, event):
        """mouse button released"""
        self.pressed = False
        self.move_line(event)
        self.picked_times, self.picked_signal = self.get_picked_data()

    def move_line(self, event):
        """move the nearest line"""
        click = event.xdata
        if abs(click - self.start) < abs(click - self.finish):
            self.start = click
        else:
            self.finish = click

    def get_picked_data(self):
        """return picked data"""
        pick = np.logical_and(self.start <= self.times,
                              self.times <= self.finish)
        times = np.extract(pick, self.times)
        signal = np.extract(pick, self.signal)
        absmax = np.max(np.abs(signal))
        return times, signal / absmax

    def plot(self, ax):
        """plot the signal over time"""
        title = ax.get_title()
        ax.clear()
        ax.set_title(title)
        ax.axvspan(self.start, self.finish, alpha=0.4, color=self.color)
        ax.plot(self.times, self.signal, color=self.color)

    def plot_clicks(self, ax):
        """plot click histogram"""
        ax.clear()
        ax.set_title('time picks')
        min_, max_, mean, std = self.time_picks()
        range_ = np.linspace(min_ - 2 * std, max_ + 2 * std, 50)
        norm_ = norm.pdf(range_, mean, std)
        ax.hist(np.array(self.picks), normed=True, color=self.color, alpha=0.6)
        ax.plot(range_, norm_, '--', c=self.color, lw=2)
        ax.set_title('Time ({} clicks)\n{:5g}±{:5g}'.format(
            len(self.picks), mean, std))
        ax.set_xlabel(r'$\mu$s')

    def plot_velocity(self, ax):
        """plot Monte Carlo velocity distribution"""
        ax.clear()
        plt.sca(ax)
        velocity = self.mc_velocity()
        velocity.plot(color=self.color, lw=2, ls='dashed')
        velocity.plot(hist=True, color=self.color, alpha=0.6)
        ax.set_title('Velocity\n{:5g}±{:5g}'.format(
            velocity.mean, velocity.std))
        ax.set_xlabel('m/s')

    def plot_bulk(self, ax):
        """plot Monte Carlo bulk modulus distribution"""
        ax.clear()
        ax.set_title('bulk modulus')
        plt.sca(ax)
        bulk = self.bulk_modulus()
        bulk.plot(color=self.color, lw=2, ls='dashed')
        bulk.plot(hist=True, color=self.color, alpha=0.6)
        ax.set_xlabel('$K$ (GPa)')

    def plot_poisson(self, ax):
        """plot Monte Carlo Poisson's ratio distribution"""
        ax.clear()
        ax.set_title("Poisson's ratio")
        plt.sca(ax)
        poisson = self.poissons_ratio()
        poisson.plot(color=self.color, lw=2, ls='dashed')
        poisson.plot(hist=True, color=self.color, alpha=0.6)
        ax.set_xlabel('$v$')

    def plot_youngs(self, ax):
        """plot Monte Carlo Young's modulus distribution"""
        ax.clear()
        ax.set_title("Young's modulus")
        plt.sca(ax)
        youngs = self.young_modulus()
        youngs.plot(color=self.color, lw=2, ls='dashed')
        youngs.plot(hist=True, color=self.color, alpha=0.6)
        ax.set_xlabel('$E$ (GPa)')

    def hilbert_angle(self):
        """get the angle of the hilbert transform"""
        return np.angle(hilbert(self.picked_signal)) / np.pi

    def hilbert_abs(self):
        """get the absolute value of the hilbert transform"""
        return np.abs(hilbert(self.picked_signal))

    def time_picks(self):
        """return picked time data"""
        if self.picks:
            time_picks = np.array(self.picks)
            return np.min(time_picks), np.max(time_picks), np.mean(time_picks), np.std(time_picks)
        return -1, 1, 0, 0.25

    def mc_velocity(self):
        """calculate velocity using Monte Carlo error propagation"""
        time_mean, time_std = self.time_picks()[2:]
        time = mc.Normal(time_mean, time_std) if time_std > 0 else time_mean
        distance = self.length
        return (distance / time) * 1e4

    def bulk_modulus(self):
        """calculate bulk modulus"""
        rho = self.density
        v = self.mc_velocity()
        mu = self.shear
        return (1e-6 * rho * v**2) - ((4/3) * mu)

    def young_modulus(self):
        """calculate young modulus"""
        mu = self.shear
        k = self.bulk_modulus()
        return (3*k - 2*mu) / (2*(3*k + mu))

    def poissons_ratio(self):
        """calculate Poisson's ratio"""
        mu = self.shear
        k = self.bulk_modulus()
        return (9*k*mu) / (3*k + mu)


def parse_args():
    """parse poropyck args"""
    resource_filename(Requirement.parse('poropyck'),
                      'poropyck/demo/NM11_2087_4A_sat.csv')

    parser = argparse.ArgumentParser(
        description='poropyck: wave velocity tool')
    parser.add_argument(
        '-t', '--template',
        help='the CSV file containing template signal data',
        default=resource_filename(Requirement.parse(
            'poropyck'), 'poropyck/demo/NM11_2087_4A_dry.csv'),
        metavar='TEMPLATE_CSV')
    parser.add_argument(
        '-q', '--query',
        help='the CSV file containing query signal data',
        default=resource_filename(Requirement.parse(
            'poropyck'), 'poropyck/demo/NM11_2087_4A_sat.csv'),
        metavar='QUERY_CSV')
    parser.add_argument(
        '-m', '--metadata',
        help='a JSON file containing sample metadata',
        default=resource_filename(Requirement.parse(
            'poropyck'), 'poropyck/demo/NM11_2087_4A_meta.json'),
        metavar='METADATA')
    return parser.parse_args()


def main():
    """the main poropyck code"""
    args = parse_args()

    with open(args.metadata) as dat:
        metadata = json.load(dat)
    mc_length = mc.Normal(
        np.mean(metadata['length']['raw']),
        np.std(metadata['length']['raw'])
    )
    # Dry (template)
    mc_density = mc.Normal(
        metadata['density']['dry']['mean'],
        metadata['density']['dry']['std']
    )
    mc_shear = mc.Normal(
        metadata['shear']['dry']['mu'],
        metadata['shear']['dry']['d_mu']
    )
    template = Signal(
        np.loadtxt(args.template, delimiter=',', skiprows=21).T[:2],
        mc_length,
        mc_density,
        mc_shear,
        color=TEMPLATE_COLOR
    )
    # Saturated (query)
    mc_density = mc.Normal(
        metadata['density']['sat']['mean'],
        metadata['density']['sat']['std']
    )
    mc_shear = mc.Normal(
        metadata['shear']['sat']['mu'],
        metadata['shear']['sat']['d_mu']
    )
    query = Signal(
        np.loadtxt(args.query, delimiter=',', skiprows=21).T[:2],
        mc_length,
        mc_density,
        mc_shear,
        color=QUERY_COLOR
    )
    Poropyck(template, query, mc_length)


if __name__ == "__main__":
    main()