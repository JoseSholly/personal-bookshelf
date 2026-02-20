from django.db import migrations, models
import django.db.models.deletion
from pgvector.django import VectorField, IvfflatIndex


class Migration(migrations.Migration):

    dependencies = [
        ("books", "0001_initial"),
        # The VectorExtension() must already be installed — handled by
        # accounts/0002_auto_20260220_2115.py which runs first because
        # books depends on auth which depends on contenttypes, but we
        # still need the extension before we create the VectorField.
        # On Railway / prod the extension migration runs first; locally
        # both share the same postgres db so it's fine.
    ]

    operations = [
        migrations.CreateModel(
            name="BookEmbedding",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "user_book",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="embedding",
                        to="books.userbook",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="book_embeddings",
                        to="auth.user",
                    ),
                ),
                (
                    "content",
                    models.TextField(help_text="The plain-text that was embedded."),
                ),
                ("embedding", VectorField(dimensions=768)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
        ),
        # IVFFlat index for fast cosine-distance nearest-neighbour search.
        # lists=100 is a good starting point; tune once the table has >1 M rows.
        migrations.AddIndex(
            model_name="bookembedding",
            index=IvfflatIndex(
                fields=["embedding"],
                name="bookembedding_embedding_ivfflat",
                lists=100,
                opclasses=["vector_cosine_ops"],
            ),
        ),
    ]
