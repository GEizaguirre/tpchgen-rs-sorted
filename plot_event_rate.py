import pandas as pd
import matplotlib.pyplot as plt
import argparse
import os

def plot_event_rate(log_file):
    if not os.path.exists(log_file):
        print(f"Error: {log_file} not found.")
        return

    # Read the log file
    # Format: timestamp, file_path
    df = pd.read_csv(log_file, names=['timestamp', 'file_path'], skipinitialspace=True)
    
    # Extract table name from file_path (e.g. sf1/lineitem/lineitem.1.parquet -> lineitem)
    df['table'] = df['file_path'].apply(lambda x: os.path.basename(os.path.dirname(x)))
    
    # Convert timestamp to datetime
    df['datetime'] = pd.to_datetime(df['timestamp'], unit='s')
    df.set_index('datetime', inplace=True)
    
    start_time = df.index.min()
    
    plt.figure(figsize=(14, 7))
    
    # Premium colors
    colors = ['#1f77b4', '#ff7f0e', '#2ca02c']
    
    print(f"\nStats:")
    print(f"{'Table':<15} | {'Total':<10} | {'Avg Rate':<10} | {'Peak Rate':<10}")
    print("-" * 55)

    for i, (table_name, group) in enumerate(df.groupby('table')):
        # Resample to 100ms intervals and count events
        event_rate = group.resample('100ms').size()
        
        # Scale counts to Events Per Second (since bin is 0.1s)
        event_rate = event_rate * 10
        
        # Calculate elapsed time in seconds from the start
        elapsed_seconds = (event_rate.index - start_time).total_seconds()
        
        color = colors[i % len(colors)]
        plt.plot(elapsed_seconds, event_rate.values, label=table_name, color=color, linewidth=2, alpha=0.8)
        
        print(f"{table_name:<15} | {len(group):<10} | {event_rate.mean():.2f} | {event_rate.max()}")

    # Premium Styling
    plt.title('Multi-Table Event Rate Over Time', fontsize=16, fontweight='bold', pad=20)
    plt.xlabel('Elapsed Time (seconds)', fontsize=12)
    plt.ylabel('Events per Second (EPS)', fontsize=12)
    plt.legend(title="Tables", fontsize=10)
    plt.grid(True, linestyle='--', alpha=0.7)
    plt.gca().set_facecolor('#fdfdfd')
    plt.tight_layout()
    
    # Save the plot
    output_plot = 'multi_event_rate.png'
    plt.savefig(output_plot, dpi=300)
    print(f"\nPlot saved to {output_plot}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Plot event rate for multiple tables")
    parser.add_argument("--log-file", type=str, default="upload.log", help="Path to the log file")
    args = parser.parse_args()
    
    plot_event_rate(args.log_file)
