import os, sys

from bmtk.simulator import pointnet


def main(config_file):
    configure = pointnet.Config.from_json(config_file)
    configure.build_env()

    network = pointnet.PointNetwork.from_config(configure)
    sim = pointnet.PointSimulator.from_config(configure, network)
    sim.run()


if __name__ == '__main__':
    if __file__ != sys.argv[-1]:
        main(sys.argv[-1])
    else:
        main('config.json')
