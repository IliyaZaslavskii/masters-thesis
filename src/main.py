class Battery():
    def __init__(self, e_cr, soc_max, soc_min, r_power_ch, r_power_ds, eff, aux_power):
        self.e_cr = e_cr
        self.soc_max = soc_max
        self.soc_min = soc_min
        self.r_power_ch = r_power_ch
        self.r_power_ds = r_power_ds