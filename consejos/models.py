from django.db import models


class Consejo(models.Model):
    id = models.BigAutoField(primary_key=True)
    titulo = models.CharField(max_length=255)
    descripcion = models.TextField()

    created_at = models.DateTimeField(
        null=True,
        blank=True,
        editable=False,
        auto_now_add=True
    )

    updated_at = models.DateTimeField(
        null=True,
        blank=True,
        editable=False,
        auto_now=True
    )

    class Meta:
        db_table = 'consejos'
        managed = False

    def __str__(self):
        return self.titulo