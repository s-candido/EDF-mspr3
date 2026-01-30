"""
Interactive web UI for visualizing and comparing energy consumption data using Streamlit.

Features:
- Connect to PostgreSQL database
- Dynamic column selection
- Interactive time series plots
- Comparison graphs
- Multiple visualization options
"""

import streamlit as st
import pandas as pd
import psycopg2
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
from datetime import datetime, timedelta
import numpy as np
from typing import Dict, List, Optional
import warnings

warnings.filterwarnings("ignore")

# Configuration
DB_CONFIG = {
    "host": "localhost",
    "database": "postgres",
    "user": "postgres",
    "password": "postgres",
    "port": 5441,
}

PREDICT_TABLE = "batch_predictions_[2020]_30_01_2026"
TRUE_TABLE = "agg_conso_meteo_features"


class ConsumptionDataInterface:
    """Interface to fetch consumption data from PostgreSQL."""
    
    def __init__(self, db_config: Dict):
        self.db_config = db_config
        self.conn = None
        self.predict_df = None
        self.actual_df = None
    
    def connect(self) -> bool:
        """Establish connection to PostgreSQL database."""
        try:
            self.conn = psycopg2.connect(**self.db_config)
            return True
        except psycopg2.Error as e:
            st.error(f"Database connection failed: {e}")
            return False
    
    def disconnect(self):
        """Close database connection."""
        if self.conn:
            self.conn.close()
    
    def _quote_identifier(self, identifier: str) -> str:
        """Quote table or column identifiers for PostgreSQL."""
        return f'"{identifier}"'
    
    def fetch_predictions(
        self,
        table_name: str = PREDICT_TABLE,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> pd.DataFrame:
        """Fetch predicted consumption data from database."""
        try:
            quoted_table = self._quote_identifier(table_name)
            query = f"SELECT * FROM {quoted_table}"
            
            if start_date or end_date:
                conditions = []
                if start_date:
                    conditions.append(f"datetime >= '{start_date}'")
                if end_date:
                    conditions.append(f"datetime <= '{end_date}'")
                query += " WHERE " + " AND ".join(conditions)
            
            query += " ORDER BY datetime"
            
            self.predict_df = pd.read_sql_query(query, self.conn)
            
            if 'datetime' in self.predict_df.columns:
                self.predict_df['datetime'] = pd.to_datetime(self.predict_df['datetime'])
            
            return self.predict_df
        
        except Exception as e:
            st.error(f"Error fetching predictions: {e}")
            return pd.DataFrame()
    
    def fetch_actual(
        self,
        table_name: str = TRUE_TABLE,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> pd.DataFrame:
        """Fetch actual consumption data from database."""
        try:
            quoted_table = self._quote_identifier(table_name)
            query = f"SELECT * FROM {quoted_table}"
            
            if start_date or end_date:
                conditions = []
                if start_date:
                    conditions.append(f"datetime >= '{start_date}'")
                if end_date:
                    conditions.append(f"datetime <= '{end_date}'")
                query += " WHERE " + " AND ".join(conditions)
            
            query += " ORDER BY datetime"
            
            self.actual_df = pd.read_sql_query(query, self.conn)
            
            if 'datetime' in self.actual_df.columns:
                self.actual_df['datetime'] = pd.to_datetime(self.actual_df['datetime'])
            
            return self.actual_df
        
        except Exception as e:
            st.error(f"Error fetching actual data: {e}")
            return pd.DataFrame()
    
    def merge_data(self) -> pd.DataFrame:
        """Merge predicted and actual data on datetime."""
        if self.predict_df is None or self.actual_df is None:
            return pd.DataFrame()
        
        merged = pd.merge(
            self.predict_df[['datetime', 'prediction']],
            self.actual_df[['datetime', 'consommation']],
            on='datetime',
            how='inner'
        )
        
        return merged
    
    def calculate_metrics(self, merged_df: pd.DataFrame) -> Dict[str, float]:
        """Calculate performance metrics."""
        if merged_df.empty:
            return {}
        
        y_true = merged_df['consommation']
        y_pred = merged_df['prediction']
        
        mae = np.mean(np.abs(y_true - y_pred))
        rmse = np.sqrt(np.mean((y_true - y_pred) ** 2))
        mape = np.mean(np.abs((y_true - y_pred) / y_true)) * 100
        
        return {
            'MAE': mae,
            'RMSE': rmse,
            'MAPE': mape,
            'Mean_Actual': y_true.mean(),
            'Mean_Predicted': y_pred.mean()
        }


def plot_consumption_comparison(merged_df: pd.DataFrame) -> go.Figure:
    """Create interactive comparison plot."""
    fig = make_subplots(
        rows=2, cols=1,
        subplot_titles=("Consumption Comparison", "Prediction Error"),
        vertical_spacing=0.12
    )
    
    fig.add_trace(
        go.Scatter(
            x=merged_df['datetime'],
            y=merged_df['consommation'],
            name='Actual Consumption',
            mode='lines',
            line=dict(color='#2E86AB', width=2),
            hovertemplate='<b>Actual</b><br>Date: %{x}<br>Consumption: %{y:.2f} kWh<extra></extra>'
        ),
        row=1, col=1
    )
    
    fig.add_trace(
        go.Scatter(
            x=merged_df['datetime'],
            y=merged_df['prediction'],
            name='Predicted Consumption',
            mode='lines',
            line=dict(color='#A23B72', width=2, dash='dash'),
            hovertemplate='<b>Predicted</b><br>Date: %{x}<br>Consumption: %{y:.2f} kWh<extra></extra>'
        ),
        row=1, col=1
    )
    
    residuals = merged_df['prediction'] - merged_df['consommation']
    fig.add_trace(
        go.Scatter(
            x=merged_df['datetime'],
            y=residuals,
            name='Prediction Error',
            mode='lines',
            line=dict(color='#C1121F', width=1.5),
            fill='tozeroy',
            hovertemplate='<b>Error</b><br>Date: %{x}<br>Error: %{y:.2f} kWh<extra></extra>'
        ),
        row=2, col=1
    )
    
    fig.add_hline(y=0, line_dash="dash", line_color="black", row=2, col=1)
    
    fig.update_xaxes(title_text="Date", row=2, col=1)
    fig.update_yaxes(title_text="Consumption (kWh)", row=1, col=1)
    fig.update_yaxes(title_text="Error (kWh)", row=2, col=1)
    
    fig.update_layout(
        height=700,
        hovermode='x unified',
        template='plotly_white',
        font=dict(size=11)
    )
    
    return fig


def plot_column_over_time(df: pd.DataFrame, column: str, title: str = None) -> go.Figure:
    """Create interactive plot for any column over time."""
    if column not in df.columns or 'datetime' not in df.columns:
        st.error(f"Column '{column}' or 'datetime' not found in data")
        return None
    
    fig = go.Figure()
    
    fig.add_trace(
        go.Scatter(
            x=df['datetime'],
            y=df[column],
            name=column,
            mode='lines',
            line=dict(color='#2E86AB', width=2),
            fill='tozeroy',
            hovertemplate=f'<b>{column}</b><br>Date: %{{x}}<br>Value: %{{y:.2f}}<extra></extra>'
        )
    )
    
    fig.update_layout(
        title=title or f"{column} Over Time",
        xaxis_title="Date",
        yaxis_title=column,
        height=500,
        hovermode='x unified',
        template='plotly_white',
        font=dict(size=11)
    )
    
    return fig


def plot_multiple_columns(df: pd.DataFrame, columns: List[str], title: str = None) -> go.Figure:
    """Create interactive plot for multiple columns."""
    fig = go.Figure()
    
    colors = px.colors.qualitative.Set1
    
    for idx, column in enumerate(columns):
        if column in df.columns and column != 'datetime':
            fig.add_trace(
                go.Scatter(
                    x=df['datetime'],
                    y=df[column],
                    name=column,
                    mode='lines',
                    line=dict(color=colors[idx % len(colors)], width=2),
                    hovertemplate=f'<b>{column}</b><br>Date: %{{x}}<br>Value: %{{y:.2f}}<extra></extra>'
                )
            )
    
    fig.update_layout(
        title=title or "Multi-Column Comparison",
        xaxis_title="Date",
        yaxis_title="Values",
        height=600,
        hovermode='x unified',
        template='plotly_white',
        font=dict(size=11),
        legend=dict(x=0.01, y=0.99)
    )
    
    return fig


def plot_scatter(merged_df: pd.DataFrame) -> go.Figure:
    """Create scatter plot of predicted vs actual."""
    fig = go.Figure()
    
    fig.add_trace(
        go.Scatter(
            x=merged_df['consommation'],
            y=merged_df['prediction'],
            mode='markers',
            marker=dict(size=5, color='#2E86AB', opacity=0.6),
            name='Data Points',
            hovertemplate='<b>Consumption</b><br>Actual: %{x:.2f}<br>Predicted: %{y:.2f}<extra></extra>'
        )
    )
    
    # Perfect prediction line
    min_val = min(merged_df['consommation'].min(), merged_df['prediction'].min())
    max_val = max(merged_df['consommation'].max(), merged_df['prediction'].max())
    
    fig.add_trace(
        go.Scatter(
            x=[min_val, max_val],
            y=[min_val, max_val],
            mode='lines',
            line=dict(color='red', width=2, dash='dash'),
            name='Perfect Prediction',
            hovertemplate='<extra></extra>'
        )
    )
    
    correlation = np.corrcoef(merged_df['consommation'], merged_df['prediction'])[0, 1]
    r_squared = correlation ** 2
    
    fig.update_layout(
        title=f"Predicted vs Actual Consumption (R² = {r_squared:.4f})",
        xaxis_title="Actual Consumption (kWh)",
        yaxis_title="Predicted Consumption (kWh)",
        height=600,
        hovermode='closest',
        template='plotly_white',
        font=dict(size=11)
    )
    
    return fig


@st.cache_resource
def init_interface():
    """Initialize interface (cached)."""
    return ConsumptionDataInterface(DB_CONFIG)


def main():
    st.set_page_config(
        page_title="Energy Consumption Dashboard",
        page_icon="⚡",
        layout="wide",
        initial_sidebar_state="expanded"
    )
    
    st.title("⚡ Energy Consumption Analysis Dashboard")
    st.markdown("---")
    
    # Sidebar configuration
    with st.sidebar:
        st.header("Configuration")
        
        interface = init_interface()
        
        if not interface.connect():
            st.error("Cannot connect to database. Check your connection settings.")
            return
        
        st.success("✓ Database connected")
        
        # Date range selection
        st.subheader("Date Range")
        col1, col2 = st.columns(2)
        
        with col1:
            start_date = st.date_input(
                "Start Date",
                value=datetime(2020, 1, 1),
                key="start_date"
            )
        
        with col2:
            end_date = st.date_input(
                "End Date",
                value=datetime(2020, 1, 31),
                key="end_date"
            )
        
        # Fetch button
        if st.button("📊 Fetch Data", key="fetch_btn"):
            st.session_state.fetch_data = True
        
        # Visualization type selection
        st.subheader("Visualization Type")
        viz_type = st.radio(
            "Select visualization:",
            ["Consumption Comparison", "Column Analysis", "Multi-Column Analysis", "Scatter Plot"]
        )
        
        st.session_state.viz_type = viz_type
    
    # Main content area
    if "fetch_data" in st.session_state and st.session_state.fetch_data:
        with st.spinner("Loading data..."):
            interface = init_interface()
            interface.connect()
            
            # Fetch data
            predict_df = interface.fetch_predictions(start_date=start_date, end_date=end_date)
            actual_df = interface.fetch_actual(start_date=start_date, end_date=end_date)
            
            if predict_df.empty or actual_df.empty:
                st.error("No data found for the selected date range")
                interface.disconnect()
                return
            
            interface.disconnect()
            
            # Store in session state
            st.session_state.predict_df = predict_df
            st.session_state.actual_df = actual_df
            st.session_state.predict_df_all = predict_df
            st.session_state.actual_df_all = actual_df
        
        st.success(f"✓ Loaded {len(predict_df)} prediction records and {len(actual_df)} actual records")
    
    # Display visualizations
    if "predict_df" in st.session_state and "actual_df" in st.session_state:
        predict_df = st.session_state.predict_df
        actual_df = st.session_state.actual_df
        
        viz_type = st.session_state.get("viz_type", "Consumption Comparison")
        
        if viz_type == "Consumption Comparison":
            st.subheader("📈 Predicted vs Actual Consumption")
            
            merged_df = pd.merge(
                predict_df[['datetime', 'prediction']],
                actual_df[['datetime', 'consommation']],
                on='datetime',
                how='inner'
            )
            
            # Display metrics
            col1, col2, col3, col4, col5 = st.columns(5)
            
            interface = ConsumptionDataInterface(DB_CONFIG)
            metrics = interface.calculate_metrics(merged_df)
            
            with col1:
                st.metric("MAE", f"{metrics.get('MAE', 0):.2f} kWh")
            with col2:
                st.metric("RMSE", f"{metrics.get('RMSE', 0):.2f} kWh")
            with col3:
                st.metric("MAPE", f"{metrics.get('MAPE', 0):.2f}%")
            with col4:
                st.metric("Avg Actual", f"{metrics.get('Mean_Actual', 0):.2f} kWh")
            with col5:
                st.metric("Avg Predicted", f"{metrics.get('Mean_Predicted', 0):.2f} kWh")
            
            st.plotly_chart(plot_consumption_comparison(merged_df), use_container_width=True)
            
            # Scatter plot
            st.subheader("🎯 Correlation Analysis")
            st.plotly_chart(plot_scatter(merged_df), use_container_width=True)
        
        elif viz_type == "Column Analysis":
            st.subheader("📊 Single Column Analysis")
            
            # Get available columns from actual_df
            available_cols = [col for col in actual_df.columns if col != 'datetime']
            
            selected_column = st.selectbox(
                "Select Column to Visualize:",
                available_cols,
                key="single_column"
            )
            
            if selected_column:
                st.plotly_chart(
                    plot_column_over_time(actual_df, selected_column),
                    use_container_width=True
                )
                
                # Display statistics
                col1, col2, col3, col4 = st.columns(4)
                data = actual_df[selected_column].dropna()
                
                with col1:
                    st.metric("Mean", f"{data.mean():.2f}")
                with col2:
                    st.metric("Min", f"{data.min():.2f}")
                with col3:
                    st.metric("Max", f"{data.max():.2f}")
                with col4:
                    st.metric("Std Dev", f"{data.std():.2f}")
        
        elif viz_type == "Multi-Column Analysis":
            st.subheader("📉 Multiple Columns Comparison")
            
            available_cols = [col for col in actual_df.columns if col != 'datetime']
            
            selected_columns = st.multiselect(
                "Select Columns to Compare:",
                available_cols,
                default=available_cols[:3],
                key="multi_column"
            )
            
            if selected_columns:
                st.plotly_chart(
                    plot_multiple_columns(actual_df, selected_columns),
                    use_container_width=True
                )
                
                # Display statistics table
                st.subheader("Statistics")
                stats_data = actual_df[selected_columns].describe().T
                st.dataframe(stats_data, use_container_width=True)
        
        elif viz_type == "Scatter Plot":
            st.subheader("🎯 Prediction Accuracy")
            
            merged_df = pd.merge(
                predict_df[['datetime', 'prediction']],
                actual_df[['datetime', 'consommation']],
                on='datetime',
                how='inner'
            )
            
            st.plotly_chart(plot_scatter(merged_df), use_container_width=True)
            
            # Display correlation info
            col1, col2 = st.columns(2)
            correlation = np.corrcoef(merged_df['consommation'], merged_df['prediction'])[0, 1]
            r_squared = correlation ** 2
            
            with col1:
                st.metric("Correlation", f"{correlation:.4f}")
            with col2:
                st.metric("R² Score", f"{r_squared:.4f}")
    
    else:
        st.info("👈 Click 'Fetch Data' in the sidebar to load data and start analyzing")
    
    # Footer
    st.markdown("---")
    st.markdown(
        """
        <div style='text-align: center'>
            <small>Energy Consumption Analysis Dashboard | Data from PostgreSQL | Built with Streamlit</small>
        </div>
        """,
        unsafe_allow_html=True
    )


if __name__ == "__main__":
    main()
