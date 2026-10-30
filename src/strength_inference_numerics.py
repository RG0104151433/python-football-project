"""Deterministic strict retries of the SAME date after restoring prior state.

This extends the adopted numerical algorithm where its default EP fails. It
does not change a successful default update, parameters, outcomes or seeds.
"""
import numpy as np
from src.strength.collapsed_jump import CollapsedJumpFilter
from src.strength.filter import NumericalFailure

RETRY_EVENTS=[]


class ReliableJumpFilter(CollapsedJumpFilter):
    def day(self,day,games):
        prior=dict(mean=self.mean.copy(),cov=self.cov.copy(),last=self.last.copy(),counts=self.counts.copy(),
            parent=self.parent.copy(),last_day=self.last_day,days=self.days,diagnostics_length=len(self.diagnostics))
        original=dict(self.numerics)
        attempts=[None,dict(ep_damping=.25,ep_max_iter=1500,ep_tolerance=1e-7),
            dict(ep_damping=.1,ep_max_iter=6000,ep_tolerance=1e-8)]
        errors=[]
        for number,settings in enumerate(attempts):
            if number:
                for field in ('mean','cov','last','counts','parent'):
                    setattr(self,field,prior[field].copy())
                self.last_day=prior['last_day'];self.days=prior['days']
                del self.diagnostics[prior['diagnostics_length']:]
                self.numerics={**original,**settings}
            try:
                result=super().day(day,games)
                if number:RETRY_EVENTS.append(dict(date=day,retries=number,settings=settings,original_errors=errors,
                    same_games_and_outcomes=True,prior_state_restored=True))
                self.numerics=original
                return result
            except NumericalFailure as error:
                errors.append(str(error))
        self.numerics=original
        raise NumericalFailure('STRICT_SAME_DATE_RETRIES_EXHAUSTED: '+repr(errors))
