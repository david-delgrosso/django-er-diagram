from django.db import models


class Author(models.Model):
    name = models.CharField(max_length=100)


class Book(models.Model):
    title = models.CharField(max_length=200)
    author = models.ForeignKey(Author, on_delete=models.CASCADE)


class Review(models.Model):
    book = models.ForeignKey(Book, on_delete=models.CASCADE)
    review_text = models.TextField()


class Grade(models.Model):
    review = models.OneToOneField(Review, on_delete=models.PROTECT)
    letter = models.CharField(max_length=1)


class Reader(models.Model):
    book = models.ManyToManyField(Book)
    name = models.CharField(max_length=50)
