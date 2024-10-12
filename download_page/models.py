from django.db import models

# Create your models here.


class Recent(models.Model):
    link = models.SlugField()
    date_time = models.DateTimeField()

    def __str__(self):
        return self.link
