import pandas as pd
import decimal
import logging
from typing import List, Dict, Any, Set

logger = logging.getLogger(__name__)

class DataJoiner:
  
    def execute_join_plan(self, execution_results: List[Dict], join_plan: List[List[Dict]]) -> List[Dict]:
       
        if not execution_results:
            return []

        # Create a fast lookup map from query_id to its data result
        data_map = {res['query_id']: res['data'] for res in execution_results}
        
        # Keep track of which query_ids are used in joins
        processed_query_ids: Set[int] = set()
        
        final_tables: List[Dict] = []


        # 1. Process all join groups
        for i, join_group in enumerate(join_plan):
            merged_df = self._perform_join_group(join_group, data_map)
            
            # Add the query_ids from this group to the processed set
            for join_info in join_group:
                processed_query_ids.add(join_info['query_id'])

            # Standardize the output and give it a name
            table_name = f"Joined Data ({i + 1})"
            standardized_table = self._standardize_dataframe_output(merged_df, table_name)
            final_tables.append(standardized_table)


        # 2. Process all standalone results that were not part of any join
        n = 1
        for res in execution_results:
            if res['query_id'] not in processed_query_ids:
                # This data is already in the standard format, just needs a name
                table_name = f"Un-Joined Data ({n})"
                standalone_table = {"table_name": table_name, **res['data']}
                final_tables.append(standalone_table)
                n += 1

        return final_tables

    # MIGHT NEED SOME FUTURE CHECKING TO HANDLE JOINS MORE EFFECTIVELY
    # MIGHT NEED A EXPLICIT JOIN TYPE AND SEQUENTIAL KEY 
    def _perform_join_group(self, join_group: List[Dict], data_map: Dict[int, Dict]) -> pd.DataFrame:
        """
        Executes a single multi-step join operation for one join group.
        """
        if not join_group:
            return pd.DataFrame()

        # Designate the first query's result as the anchor (left) DataFrame
        anchor_info = join_group[0]
        anchor_df = pd.DataFrame(data_map[anchor_info['query_id']]['rows'])
        
        # Sequentially -join the rest of the queries in the group
        for i in range(1, len(join_group)):
            right_info = join_group[i]
            right_df = pd.DataFrame(data_map[right_info['query_id']]['rows'])
            
            # Perform the merge
            anchor_df = pd.merge(
                anchor_df,
                right_df,
                left_on=anchor_info['key'],
                right_on=right_info['key'],
                how='inner',
                suffixes=('', '_right') # Suffix to handle overlapping column names
            )

            # Drop the redundant join key from the right table
            if right_info['key'] != anchor_info['key']:
                 anchor_df = anchor_df.drop(columns=[right_info['key']])
            
            # Drop any other overlapping columns that were suffixed
            suffixed_cols = [col for col in anchor_df.columns if col.endswith('_right')]
            anchor_df = anchor_df.drop(columns=suffixed_cols)

        return anchor_df

    def _standardize_dataframe_output(self, df: pd.DataFrame, table_name: str) -> Dict[str, Any]:
        def make_serializable(val):
            if isinstance(val, decimal.Decimal):
                return float(val)
            elif isinstance(val, (pd.Timestamp, pd.Timedelta)):
                return str(val)
            return val
    
        rows = [
            {k: make_serializable(v) for k, v in row.items()}
            for row in df.to_dict(orient='records')
        ]
        # Infer column types from the DataFrame dtypes
        columns = []
        for col_name, dtype in df.dtypes.items():
            col_type = str(dtype)
            # Make dtypes more JS-friendly
            if 'int' in col_type:
                col_type = 'integer'
            elif 'float' in col_type:
                col_type = 'float'
            elif 'datetime' in col_type:
                col_type = 'datetime'
            else:
                col_type = 'string'
            columns.append({"name": col_name, "type": col_type})
    
        return {
            "table_name": table_name,
            "columns": columns,
            "rows": rows,
            "row_count": len(rows)
        }