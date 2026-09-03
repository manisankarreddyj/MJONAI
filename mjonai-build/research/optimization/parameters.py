from __future__ import annotations

from itertools import product

from research.optimization.models import (
    ParameterDefinition,
    ParameterSet,
)


class ParameterGrid:

    def __init__(
        self,
        parameters: list[ParameterDefinition],
    ) -> None:

        self._parameters = parameters

    def generate(
        self,
    ) -> list[ParameterSet]:

        if not self._parameters:
            return [
                ParameterSet(
                    values={},
                )
            ]

        names = [
            parameter.name
            for parameter in self._parameters
        ]

        value_lists = [
            parameter.values
            for parameter in self._parameters
        ]

        combinations: list[
            ParameterSet
        ] = []

        for values in product(
            *value_lists,
        ):

            combinations.append(
                ParameterSet(
                    values=dict(
                        zip(
                            names,
                            values,
                        )
                    )
                )
            )

        return combinations

    def count(
        self,
    ) -> int:

        total = 1

        for parameter in self._parameters:
            total *= len(
                parameter.values
            )

        return total