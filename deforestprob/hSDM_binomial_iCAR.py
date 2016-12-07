#!/usr/bin/python

# =============================================================================
#
# hSDM_binomial_iCAR.py
#
# Function which estimates the parameters of a Binomial model with
# iCAR process for spatial autocorrelation in a hierarchical Bayesian
# framework
#
# Ghislain Vieilledent <ghislain.vieilledent@cirad.fr>
# November 2016
#
# Suitability formula:
# Of the form: y + trial ~ x1 + x2 + x3 + cell
# The last term on the right of the formula should correspond
# to the cells
#
# ============================================================================

import numpy as np
from patsy import dmatrices, build_design_matrices
import hsdm
from matplotlib.backends.backend_pdf import PdfPages
import matplotlib.pyplot as plt
from sklearn.linear_model import LogisticRegression


# Function invlogit
def invlogit(x):
    Result = 1/(1+np.exp(-x))
    return (Result)


# binomial_iCAR function
class hSDM_binomial_iCAR(object):

    def __init__(self,  # Observations
                 suitability_formula, data,
                 # Spatial structure
                 n_neighbors, neighbors,
                 # NA action
                 NA_action="drop",
                 # Predictions
                 data_pred=None,
                 # Chains
                 burnin=1000, mcmc=1000, thin=1,
                 # Starting values
                 beta_start=0,
                 Vrho_start=1,
                 # Priors
                 mubeta=0, Vbeta=1.0e6,
                 priorVrho=-1.0,  # -1="1/Gamma"
                 shape=0.5, rate=0.0005,
                 Vrho_max=10,
                 # Various
                 seed=1234, verbose=1,
                 save_rho=0, save_p=0):

        # ========
        # Form response, covariate matrices and model parameters
        # ========

        # Patsy
        y, x = dmatrices(suitability_formula, data,
                         eval_env=1, NA_action=NA_action)
        self._y_design_info = y.design_info
        self._x_design_info = x.design_info

        # Response
        Y = y[:, 0]
        nobs = len(Y)
        T = y[:, 1]
        # Suitability
        X_arr = x[:, :-1]  # We remove the last column (cells)
        ncol_X = X_arr.shape[1]
        X = X_arr.flatten("F")  # Flatten X by column (R/Fortran style)
        # Spatial correlation
        ncell = len(n_neighbors)
        cells = x[:, -1]  # Last column of x
        # Predictions
        if (data_pred is None):
            X_pred = X
            cells_pred = cells
            npred = nobs
        if (data_pred is not None):
            (x_pred,) = build_design_matrices([self._x_design_info],
                                              data_pred)
            X_pred = x_pred[:, :-1]
            X_pred = X_pred.flatten("F")  # Flatten X_pred
            cells_pred = x_pred[:, -1]
            npred = len(cells_pred)
        # Model parameters
        npar = ncol_X
        ngibbs = mcmc+burnin
        nthin = thin
        nburn = burnin
        nsamp = mcmc/thin

        # ========
        # Initial starting values for M-H
        # ========

        if (beta_start == -99):
            # Use starting coefficient from logistic regression
            print("Using estimates from classic logistic regression as"
                  " starting values for betas")
            mod_LR = LogisticRegression()
            mod_LR = mod_LR.fit(X_arr, Y)
            beta_start = np.ravel(mod_LR.coef_)
        if (np.size(beta_start) == 1 and beta_start != -99):
            beta_start = np.ones(npar) * beta_start
        else:
            beta_start = beta_start
        rho_start = np.zeros(ncell)  # Set to zero
        Vrho_start = Vrho_start

        # ========
        # Form and check priors
        # ========
        if (np.size(mubeta) == 1):
            mubeta = np.ones(npar) * mubeta
        else:
            mubeta = mubeta
        if (np.size(Vbeta) == 1):
            Vbeta = np.ones(npar) * Vbeta
        else:
            Vbeta = Vbeta
        shape = shape
        rate = rate
        Vrho_max = Vrho_max
        priorVrho = priorVrho

        # ========
        # call C code to draw sample
        # ========

        Sample = hsdm.binomial_iCAR(
            # Constants and data
            ngibbs=int(ngibbs),
            nthin=int(nthin),
            nburn=int(nburn),
            nobs=int(nobs),
            ncell=int(ncell),
            np=int(npar),
            Y_obj=Y.astype(np.int32),
            T_obj=T.astype(np.int32),
            X_obj=X.astype(np.float64),  # X must be flattened.
            # Spatial correlation
            C_obj=cells.astype(np.int32),  # Must start at 0 for C.
            nNeigh_obj=n_neighbors.astype(np.int32),
            Neigh_obj=neighbors.astype(np.int32),  # Must start at 0 for C.
            # Predictions
            npred=int(npred),
            X_pred_obj=X_pred.astype(np.float64),
            C_pred_obj=cells_pred.astype(np.int32),
            # Starting values for M-H
            beta_start_obj=beta_start.astype(np.float64),
            rho_start_obj=rho_start.astype(np.float64),
            Vrho_start=float(Vrho_start),
            # Defining priors
            mubeta_obj=mubeta.astype(np.float64),
            Vbeta_obj=Vbeta.astype(np.float64),
            priorVrho=float(priorVrho),
            shape=float(shape),
            rate=float(rate),
            Vrho_max=float(Vrho_max),
            # Seed
            seed=int(seed),
            # Verbose
            verbose=int(verbose),
            # Save rho and p
            save_rho=int(save_rho),
            save_p=int(save_p))

        # Array of MCMC samples
        MCMC = np.zeros(shape=(nsamp, npar+2))
        MCMC[:, :npar] = np.array(Sample[0]).reshape(npar, nsamp).transpose()
        MCMC[:, npar] = Sample[2]
        MCMC[:, npar+1] = Sample[3]
        self.mcmc = MCMC
        posterior_means = np.mean(MCMC, axis=0)
        self.betas = posterior_means[:-2]
        self.Vrho = posterior_means[-2]
        self.Deviance = posterior_means[-1]

        # Save rho
        if (save_rho == 0):
            self.rho = np.array(Sample[1])
        if (save_rho == 1):
            self.rho = np.array(Sample[1]).reshape(ncell, nsamp).transpose()

        # Save pred
        if (save_p == 0):
            self.theta_pred = np.array(Sample[5])
        if (save_p == 1):
            self.theta_pred = np.array(
                Sample[5]).reshape(npred, nsamp).transpose()

        # theta_latent
        self.theta_latent = np.array(Sample[4])

    def __repr__(self):
        summary = ("Binomial logistic regression with iCAR process\n"
                   "  Model: %s ~ %s\n"
                   "  Posteriors:\n"
                   % (self._y_design_info.describe(),
                      self._x_design_info.describe()))
        # Varnames
        varnames = self._x_design_info.column_names[:-1]
        varnames = np.concatenate((varnames, ["Vrho", "Deviance"]))
        nvar = len(varnames)
        name_width = max(len(x) for x in varnames)
        # Posteriors
        MCMC = self.mcmc
        post_mean = np.mean(MCMC, axis=0)
        post_std = np.std(MCMC, axis=0)
        CI_low = np.percentile(MCMC, 2.5, axis=0)
        CI_high = np.percentile(MCMC, 97.5, axis=0)
        # Titles
        summary += ("%" + str(name_width) +
                    "s %10s %10s %10s %10s\n") % ("", "Mean", "Std",
                                                  "CI_low", "CI_high")
        # Loop on varnames
        for i in range(nvar):
            summary += ("%" + str(name_width) +
                        "s %10.3g %10.3g %10.3g %10.3g\n") % (varnames[i],
                                                              post_mean[i],
                                                              post_std[i],
                                                              CI_low[i],
                                                              CI_high[i])
        return (summary)

    def predict(self, new_data):
        (new_x,) = build_design_matrices([self._x_design_info],
                                         new_data)
        new_X = new_x[:, :-1]
        new_cell = new_x[:, -1].astype(np.int)
        if (len(self.rho.shape) == 1):
            new_rho = self.rho[new_cell]
        else:
            new_rho = np.mean(self.rho, axis=0)[new_cell]
        return (invlogit(np.dot(new_X, self.betas) + new_rho))

    def plot(self, output_file="mcmc.pdf", plots_per_page=5,
             figsize=(8.27, 11.69), dpi=100):
        # Message
        print("Traces and posteriors will be plotted in " + output_file)
        # Varnames
        varnames = self._x_design_info.column_names[:-1]
        varnames = np.concatenate((varnames, ["Vrho", "Deviance"]))
        # Posterior means
        MCMC = self.mcmc
        posterior_means = np.mean(MCMC, axis=0)
        # The PDF document
        pdf_pages = PdfPages(output_file)
        # Generate the pages
        nb_plots = len(varnames)
        grid_size = (plots_per_page, 2)
        # List of figures to be returned
        figures = []
        # Loop on parameters
        for i in range(nb_plots):
            # Create a figure instance (ie. a new page) if needed
            if i % plots_per_page == 0:
                fig = plt.figure(figsize=figsize, dpi=dpi)
            # Trace
            ax = plt.subplot2grid(grid_size, (i % plots_per_page, 0))
            plt.axhline(y=posterior_means[i], linewidth=1, color="r")
            plt.plot(MCMC[:, i], color="#000000")
            plt.text(0, 1, varnames[i],
                     horizontalalignment="left",
                     verticalalignment="bottom", fontsize=11,
                     transform=ax.transAxes)
            # Posterior distribution
            plt.subplot2grid(grid_size, (i % plots_per_page, 1))
            plt.hist(MCMC[:, i], normed=1, bins=20, color="#808080")
            plt.axvline(x=posterior_means[i], linewidth=1, color="r")
            # Close the page if needed
            if (i + 1) % plots_per_page == 0 or (i + 1) == nb_plots:
                plt.tight_layout()
                figures.append(fig)
                pdf_pages.savefig(fig)
        # Write the PDF document to the disk
        pdf_pages.close()
        return (figures)

# ===================================================================
# END
# ===================================================================
