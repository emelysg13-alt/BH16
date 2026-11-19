from django.db import models


class Localidad(models.Model):
    id_localidad = models.PositiveSmallIntegerField(primary_key=True)
    n_localidad = models.CharField(max_length=100)
    poblacion = models.PositiveIntegerField(null=True, blank=True)

    class Meta:
        db_table = 'localidades'
        managed = False

    def __str__(self):
        return self.n_localidad


class Refugio(models.Model):

    ESTADOS = [
        ('activo', 'Activo'),
        ('inactivo', 'Inactivo'),
    ]

    id_refugio = models.AutoField(primary_key=True)
    nombre = models.CharField(max_length=150)
    descripcion = models.TextField(null=True, blank=True)
    direccion = models.CharField(max_length=255)
    telefono = models.CharField(max_length=20, null=True, blank=True)
    email = models.EmailField(max_length=150, null=True, blank=True)

    localidad = models.ForeignKey(
        Localidad,
        on_delete=models.PROTECT,
        db_column='localidad_id',
        related_name='refugios'
    )

    estado = models.CharField(
        max_length=8,
        choices=ESTADOS,
        default='activo',
        null=True
    )

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
        db_table = 'refugios'
        managed = False

    def __str__(self):
        return self.nombre


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
