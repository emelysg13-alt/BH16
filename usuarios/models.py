from django.db import models

class Persona(models.Model):

    TIPOS_DOCUMENTO = [
        ('CC', 'Cédula de ciudadanía'),
        ('CE', 'Cédula de extranjería'),
        ('TI', 'Tarjeta de identidad'),
        ('PP', 'Pasaporte'),
    ]

    nombres = models.CharField(max_length=100)
    apellidos = models.CharField(max_length=100)
    tipo_documento = models.CharField(
        max_length=2,
        choices=TIPOS_DOCUMENTO
    )
    numero_documento = models.CharField(
        max_length=30,
        unique=True
    )
    correo = models.EmailField(max_length=150)
    telefono = models.CharField(max_length=20)
    fecha_registro = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.nombres} {self.apellidos}"