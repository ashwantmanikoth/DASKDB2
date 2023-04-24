import dask.dataframe as dd
import re
from typing import Callable


class IterativeQueryProcessor:
    column_mappings = {}

    def __init__(self, base_code_block, iterative_code_block, final_code_block, **dataframes):
        self.dataframes = dataframes
        locals().update(self.dataframes)

        # Find the CTE name from the return statement in the final method
        cte_name_match = re.search(r'(\w+)\s*=\s*\w+\s*\.\w+\s*\(\s*\)$', final_code_block, flags=re.MULTILINE)
        if cte_name_match:
            cte_name = cte_name_match.group(1)
        else:
            cte_name = None

        self.create_function("base_query", base_code_block, [])
        self.create_function("recursive_query", iterative_code_block, [cte_name])
        self.create_function("final_query", final_code_block, [cte_name])

    def create_function(self, func_name, code_block, param_names):
        func_header = f'def {func_name}(self, ' + ', '.join(param_names) + '):\n'

        indented_code = '    '.join(code_block.splitlines(True))

        last_assignment_match = re.search(r'(\w+)\s*=\s*\w+\s*\.\w+\s*\(\s*\)$', code_block, flags=re.MULTILINE)

        if last_assignment_match:
            return_var = last_assignment_match.group(1)

        func_definition = func_header + indented_code

        exec(func_definition, globals(), locals())
        setattr(self, func_name, locals()[func_name])

    def process_iterative_query(self, max_iterations=100):
        # Add type hints for the dynamically created methods
        base_query: Callable = getattr(self, "base_query")
        recursive_query: Callable = getattr(self, "recursive_query")
        final_query: Callable = getattr(self, "final_query")

        with self:
            cte_customer_tree = base_query(self)
            iteration = 0

            while True:
                new_cte_customer_tree = recursive_query(self, cte_customer_tree)
                if new_cte_customer_tree.empty or iteration >= max_iterations:
                    break

                cte_customer_tree = dd.concat([cte_customer_tree, new_cte_customer_tree])
                iteration += 1

            result = final_query(self, cte_customer_tree)

        return result


    def add_columns_index(self, df, df_string):
        self.column_mappings[df_string] = df.columns
