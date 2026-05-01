class ReviewsController < ApplicationController
  allow_unauthenticated_access only: %i[ index show ]

  before_action :set_reviewee, only: %i[ new create ]
  before_action :set_review,   only: %i[ show destroy ]

  def index
    @reviews = Review.recent.includes(:reviewer, :reviewee).limit(50)
  end

  def show
  end

  def new
    @review = @reviewee.reviews_received.build
  end

  def create
    @review = @reviewee.reviews_received.build(review_params)
    @review.reviewer = Current.user

    unless Current.user&.can_write_reviews?
      redirect_to user_path(@reviewee), alert: "Only subcontractors can post reviews." and return
    end

    if @review.save
      redirect_to user_path(@reviewee), notice: "Review posted."
    else
      render :new, status: :unprocessable_entity
    end
  end

  def destroy
    if @review.reviewer_id == Current.user&.id
      @review.destroy
      redirect_to user_path(@review.reviewee), notice: "Review deleted."
    else
      redirect_to review_path(@review), alert: "You can only delete your own reviews."
    end
  end

  private

  def set_reviewee
    @reviewee = User.find(params[:user_id])
  end

  def set_review
    @review = Review.includes(:reviewer, :reviewee).find(params[:id])
  end

  def review_params
    params.require(:review).permit(
      :rating, :payment_timeliness, :scope_clarity, :communication,
      :would_work_again, :body, :project_description
    )
  end
end
