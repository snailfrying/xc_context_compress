import click
from pathlib import Path
from ...sdk.client import DistillerClient


@click.group()
def cli():
    """Context Distiller CLI"""
    pass


@cli.command()
@click.argument('files', nargs=-1, type=click.Path(exists=True))
@click.option('--profile', default='balanced', help='Profile: speed/balanced/accuracy')
@click.option('--output', '-o', help='Output file')
def distill(files, profile, output):
    """批量压缩文件"""
    client = DistillerClient(profile=profile)

    for file in files:
        click.echo(f"Processing {file}...")
        result = client.process(data=[str(file)])
        click.echo(f"Compression ratio: {result.stats.compression_ratio:.2%}")

    click.echo("Done!")


@cli.command()
@click.argument('query')
@click.option('--top-k', default=5, help='Top K results')
def search(query, top_k):
    """检索记忆"""
    client = DistillerClient()
    result = client.search_memory(query, top_k)

    for chunk in result['chunks']:
        click.echo(f"\n{chunk['source']}:")
        click.echo(chunk['content'][:200])


if __name__ == '__main__':
    cli()
