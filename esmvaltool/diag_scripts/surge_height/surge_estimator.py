#;;#############################################################################
#;; Surge estimator
#;; Author: Nina Nadine Ridder (KNMI, The Netherlands)
#;; C3 MAGIC project
#;;#############################################################################
#;; Description
#;;    Diagnostic to estimate surge heights from sea level pressure (msp)
#;;    and u- and v- component of 10m wind
#;;    Additional description of the diagnostic
#;;    Method to estimate surge described in  et al. ()
#;;
#;; Required diag_script_info attributes (diagnostics specific)
#;;    att1: short description
#;;          keep the indentation if more lines are needed
#;;    att2: short description
#;;
#;; Optional diag_script_info attributes (diagnostic specific)
#;;    att1: short description
#;;    att2: short description
#;;
#;; Required variable_info attributes (variable specific)
#;;    att1: short description
#;;    att2: short description
#;;
#;; Optional variable_info attributes (variable specific)
#;;    att1: short description
#;;    att2: short description
#;;
#;; Caveats
##;;    assumes psl, ua & va are provided on ERA-Interim grid
##;;    surge data generated using WAQUA/DCSMv5, which underestimates extreme
##;;    Features to-be-implemented shall also be mentioned here
##;;
##;; Modification history
##;;    YYYYMMDD-A_X4Y4: extended...
##;;    20180927-A_RN: bug-fixed...
##;;    20180522-A_RN: adapted to include module structure
##;;    20180104-A_RN: written.
##;;
##;; #############################################################################

#load ...
#load ...

#begin

import os
import pickle
import sys
from datetime import datetime

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import xarray as xr
from eofs.standard import Eof

#import .dataprep.grad_psl as dpgrd
#import .estimate.build_predictX as ebX
#import .estimate.estimate_srg as ees
#import .load.load_betas_intercept as llbi
#import .load.load_EOFs
#import .output.plot_tseries as opt
#import .output.save_netCDF as osn
from dataprep.calc_monanom import calc_monanom
from dataprep.cut_NS_xarray import cut_NS
from dataprep.grad_psl import grad_psl
from dataprep.Xtrms_xarray import Xtrms
from estimate.build_predictX import build_predictX
from estimate.estimate_srg import estimate_srg
from load.check_solver import check_solver
from load.load_betas_intercept import load_betas_intercept
from load.load_config import load_config
from load.load_EOFs import load_eofs
from output.plot_map_cartopy import plot_map_cartopy
from output.plot_tseries import plot_tseries
from output.save_netCDF import save_netCDF
#from regression.perf_regres import perf_regres


def surge_estimator_main(psl_in, uas_in, vas_in, cfg, dataset):
    # ---------------
    # I. Definitions
    # ---------------
    # I.1 Stations
    # I.1a Names
    allstats = [
        'aberdeen', 'aukalpha', 'bg2', 'borkums', 'bremerha', 'cadzand', 'cromer', 
        'cuxhaven', 'delfzijl', 'denhelde', 'denoever', 'devonpor', 'dover', 
        'duinkerk', 'ekofisk', 'esbjerg', 'europlat', 'f3', 'felixsto', 'goeree',  
        'harlinge', 'helgeroa', 'helgolan', 'hoekvanh', 'holyhead', 'huibertg',  
        'husum', 'ijmuiden', 'ilfracom', 'immingha', 'innerdow', 'k13a',  
        'kornwerd', 'lauwerso', 'leith', 'lerwick', 'lowestof', 'meetpost',  
        'newhaven', 'newlyn', 'northcor', 'northshi', 'offharwi', 'oostende',  
        'os11', 'os15', 'oscarsbo', 'portsmou', 'roompotb', 'scarboro', 'scheveni',  
        'scillyis', 'sheernes', 'southend', 'stavange', 'stmarys', 'stornowa',  
        'terschel', 'texelnoo', 'torsmind', 'tregde', 'vidaa', 'vlaktevd',  
        'vlissing', 'westkape', 'westters', 'weymouth', 'wick', 'zeebrugg'
    ]
    # I.1b Selection
    if cfg['stations'] == 'all':
        stat = allstats
    elif set(stat).issubset(allstats):
        stat = cfg['stations']
    else:
        stat = [x for x in cfg['stations'] if x in allstats]
    #
    if cfg["plt_tseries"]:
        if cfg["plt_stations"] in allstats:
            stat_tseries = cfg["plt_stations"]
        else:
            #logger.info(
            print('Station ' + str(cfg["plt_tseries"]) +
                  ' is not available -> timeseries plot cannot be generated.')
            cfg["plt_tseries"] = False

    # 2. Date for map plot
    if cfg["coastal_map"]:
        dates_map = [
            datetime(cfg['t0'].year, cfg['t0'].month, cfg['t0'].day, 0, 0)
        ]
    #
    # ---------------------------------------------------------------------------
    # II. Determine time series range and dates as if input was daily timeseries
    # ---------------------------------------------------------------------------
    dates = []
    ns = 1e-9  # number of seconds in a nanosecond
    for t in psl_in.time.values:
        tmp = datetime.utcfromtimestamp(t.astype(int) * ns)
        dates.append(datetime(tmp.year, tmp.month, tmp.day, 0, 0))

    dates = list(set(dates))
    dates.sort()

    # ----------------------------------------------------
    # III. Cut NS box & calculate daily maxes & anomalies
    # ----------------------------------------------------
    #logger.debug
    print("Preprocessing input data")

    pslNS, uaNS, vaNS = cut_NS(psl_in, uas_in, vas_in)

    xpslNS, xuaNS, xvaNS = Xtrms(pslNS, uaNS, vaNS)
    #print('after xtrms')
    #print(np.isnan(xpslNS.values.flatten()).any())

    psl, uas, vas = calc_monanom(xpslNS, xuaNS, xvaNS)
    #print('after preprocessing')
    #print(np.isnan(psl.values.flatten()).any())

    # -----------------------------
    # IV. Calculate SLP gradients
    # -----------------------------
    #logger.debug("Calculating gradient of psl")
    gradlatpsl = np.gradient(psl, axis=1)
    gradlonpsl = np.gradient(psl, axis=2)

    # -----------------------------------------------------------
    # V. Load or determine EOF solvers & load regression coefficients
    # -----------------------------------------------------------
    #logger.debug("Loading EOFs and regression coefficients")
    dirname = os.path.dirname(__file__)
    data_dir = os.path.join(dirname, 'data')

    solvers_exist = check_solver(data_dir)

    if dataset == 'ERA-Interim' and not solvers_exist:
        [psl_solver, gradlon_solver, gradlat_solver, 
          uas_solver, vas_solver] = calc_eofs(psl, uas, vas, gradlatpsl, gradlonpsl, data_dir)
        print('EOF solvers generated and saved to ' + data_dir)
        exit()
    elif not dataset == 'ERA-Interim' and not solvers_exist:
        print('No EOF solvers found. Please rerun the script with ERA-Interim to produce them.')
        exit('ERROR - no EOF solvers found')
    else:
        psl_solver, gradlon_solver, gradlat_solver, uas_solver, vas_solver = load_eofs(data_dir)

    # -----------------------------------------
    # VI. Project fields onto ERA-Interim EOFs
    # -----------------------------------------
    #logger.debug("Generating PCs")
    pseudo_pcs_slp = psl_solver.projectField(psl.values)
    pseudo_pcs_gradlatpsl = gradlat_solver.projectField(gradlatpsl)
    pseudo_pcs_gradlonpsl = gradlon_solver.projectField(gradlonpsl)
    pseudo_pcs_us = uas_solver.projectField(uas.values)
    pseudo_pcs_vs = vas_solver.projectField(vas.values)

    # -------------------------------
    # VII. Generate predictor array
    # -------------------------------
    #logger.debug("Generating predictor array")
    X = {}
    for s in stat:
        X[s] = build_predictX(
            dates,
            pseudo_pcs_slp,
            pseudo_pcs_gradlatpsl,  #...
            pseudo_pcs_gradlonpsl,
            pseudo_pcs_us,
            pseudo_pcs_vs)

    # -----------------------------------------------------------
    # VIII. Load regression coefficients or train model
    # -----------------------------------------------------------
    betas, intercept = load_betas_intercept(stat, data_dir)

    # ----------------------------
    # IX. Apply regression model
    # ----------------------------
    #logger.debug("Estimating surge heights")
    srg_estim = estimate_srg(X, dates, stat, betas, intercept)

    # ------------------------
    # X. Save surge to file
    # ------------------------
    if cfg["fout_name"] == "":
        cfg["fout_name"] = 'surge'

    if cfg["write_netcdf"]:
        #logger.debug('saving data to netCDF file ')
        save_netCDF(dates, stat, srg_estim, cfg, dataset)

    # -----------
    # XI. Plot
    # -----------
    # if write_plots:
    if cfg["coastal_map"]:  # generate geographical map with surge levels on day specified in config file
        #logger.info("Plotting and saving geographical map with surge heights")
        plot_map_cartopy(dates_map[0], srg_estim,
                         dates.index(dates_map[0]), cfg, dataset)
    #
    if cfg["plt_tseries"]:  # generate timeseries plot
        #logger.info("Plotting and saving surge timeseries")
        for s in stat_tseries:
            plot_tseries(dates, srg_estim[s], s, cfg, dataset)


if __name__ == '__main__':
    print('Is main')
    import sys
    surge_estimator_main(sys.argv[1], sys.argv[2], sys.argv[3])
